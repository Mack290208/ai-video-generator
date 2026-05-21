from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
import time
import wave
import struct
import contextlib
import requests


@dataclass
class TTSConfig:
    """GPT-SoVITS 本地 API 配置（api_v2.py）。"""
    provider: str = "gpt_sovits"
    base_url: str = "http://127.0.0.1:9880"
    ref_audio_path: str = ""
    prompt_text: str = ""
    prompt_lang: str = "zh"
    text_lang: str = "zh"
    text_split_method: str = "cut5"
    batch_size: int = 1
    media_type: str = "wav"
    streaming_mode: bool = False
    speed_factor: float = 1.0
    timeout_seconds: int = 300
    # --- 健壮性配置（A1 新增）---
    retry_attempts: int = 3            # 失败重试总次数（含首次）
    retry_backoff_seconds: float = 1.0  # 退避基数：1s, 3s, 6s ...
    health_check_enabled: bool = True   # 调用前是否做轻量探活
    silence_fallback: bool = True       # 全部重试失败时是否生成静默 wav 顶替
    silence_fallback_seconds: float = 4.0  # 静默 fallback 默认时长（秒）
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "TTSConfig":
        return cls(
            provider=os.getenv("TTS_PROVIDER", "gpt_sovits"),
            base_url=os.getenv("GPT_SOVITS_BASE_URL", "http://127.0.0.1:9880").rstrip("/"),
            ref_audio_path=os.getenv("GPT_SOVITS_REF_AUDIO", ""),
            prompt_text=os.getenv("GPT_SOVITS_PROMPT_TEXT", ""),
            prompt_lang=os.getenv("GPT_SOVITS_PROMPT_LANG", "zh"),
            text_lang=os.getenv("GPT_SOVITS_TEXT_LANG", "zh"),
            text_split_method=os.getenv("GPT_SOVITS_SPLIT", "cut5"),
            batch_size=int(os.getenv("GPT_SOVITS_BATCH_SIZE", "1")),
            media_type=os.getenv("GPT_SOVITS_MEDIA_TYPE", "wav"),
            streaming_mode=os.getenv("GPT_SOVITS_STREAMING", "false").lower() == "true",
            speed_factor=float(os.getenv("GPT_SOVITS_SPEED", "1.0")),
            timeout_seconds=int(os.getenv("GPT_SOVITS_TIMEOUT", "300")),
            retry_attempts=int(os.getenv("TTS_RETRY_ATTEMPTS", "3")),
            retry_backoff_seconds=float(os.getenv("TTS_RETRY_BACKOFF", "1.0")),
            health_check_enabled=os.getenv("TTS_HEALTH_CHECK", "true").lower() == "true",
            silence_fallback=os.getenv("TTS_SILENCE_FALLBACK", "true").lower() == "true",
            silence_fallback_seconds=float(os.getenv("TTS_SILENCE_FALLBACK_SECONDS", "4.0")),
        )


class GPTSoVITSTTSService:
    """调用本地 GPT-SoVITS api_v2.py 的 /tts 接口。"""

    def __init__(self, config: TTSConfig):
        self.config = config

    def synthesize_to_file(
        self,
        text: str,
        output_path: str | Path,
        speaker: str | None = None,           # 保留签名兼容：speaker -> 参考音频路径覆盖
        speed: float | None = None,
        ref_audio_path: str | None = None,
        prompt_text: str | None = None,
        prompt_lang: str | None = None,
        text_lang: str | None = None,
        text_split_method: str | None = None,
    ) -> dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("TTS 输入文本为空")

        ref_audio = ref_audio_path or speaker or self.config.ref_audio_path
        if not ref_audio:
            raise RuntimeError(
                "缺少参考音频路径：请在 .env 设置 GPT_SOVITS_REF_AUDIO，"
                "或在 segment 中传入 ref_audio_path / speaker。"
            )
        if not Path(ref_audio).exists():
            raise RuntimeError(f"参考音频文件不存在: {ref_audio}")

        prompt_t = (prompt_text if prompt_text is not None else self.config.prompt_text) or ""

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "text": text.strip(),
            "text_lang": (text_lang or self.config.text_lang).lower(),
            "ref_audio_path": str(ref_audio),
            "prompt_text": prompt_t,
            "prompt_lang": (prompt_lang or self.config.prompt_lang).lower(),
            "text_split_method": text_split_method or self.config.text_split_method,
            "batch_size": self.config.batch_size,
            "media_type": self.config.media_type,
            "streaming_mode": self.config.streaming_mode,
            "speed_factor": float(speed) if speed is not None else self.config.speed_factor,
        }

        # --- A1: 健康检查 + 重试 + 静默 fallback ---
        attempts: list[dict[str, Any]] = []
        audio_bytes: bytes | None = None
        used_fallback = False

        if self.config.health_check_enabled and not self._service_alive():
            print(f"[tts][warn] 健康检查失败：{self.config.base_url} 不响应；仍尝试调用一次再决定。")

        last_err: Exception | None = None
        for i in range(self.config.retry_attempts):
            try:
                audio_bytes = self._call_tts(payload)
                attempts.append({"attempt": i + 1, "ok": True})
                last_err = None
                break
            except Exception as e:
                last_err = e
                attempts.append({"attempt": i + 1, "ok": False, "error": str(e)[:300]})
                # 退避：1s, 3s, 6s ...
                if i + 1 < self.config.retry_attempts:
                    backoff = self.config.retry_backoff_seconds * (1 + 2 * i)
                    print(f"[tts][retry] attempt {i+1}/{self.config.retry_attempts} 失败：{str(e)[:200]}；{backoff:.1f}s 后重试")
                    time.sleep(backoff)

        if audio_bytes is None:
            if not self.config.silence_fallback:
                raise RuntimeError(
                    f"GPT-SoVITS 调用失败已重试 {self.config.retry_attempts} 次：{last_err}"
                )
            # 全部失败 → 写一段静默 wav 顶替
            seconds = max(1.0, float(self.config.silence_fallback_seconds))
            audio_bytes = self._make_silence_wav_bytes(seconds)
            used_fallback = True
            print(
                f"[tts][fallback] {self.config.retry_attempts} 次全部失败，写入静默 wav {seconds:.2f}s 以保 pipeline 不中断。"
                f" 最后一次错误：{str(last_err)[:300]}"
            )

        output_path.write_bytes(audio_bytes)
        duration = self._get_wav_duration_seconds(output_path)

        return {
            "duration_seconds": duration,
            "used_fallback": used_fallback,
            "attempts": attempts,
            "meta": {
                "provider": self.config.provider,
                "base_url": self.config.base_url,
                "ref_audio": str(ref_audio),
                "prompt_text": prompt_t,
                "text_lang": payload["text_lang"],
                "speed_factor": payload["speed_factor"],
                "bytes": len(audio_bytes),
            }
        }

    def _call_tts(self, payload: dict[str, Any]) -> bytes:
        url = f"{self.config.base_url}/tts"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        resp = requests.post(
            url,
            data=self._to_utf8_json(payload),
            headers=headers,
            timeout=self.config.timeout_seconds,
        )
        # 错误时 api_v2 返回 JSON；成功时返回音频二进制
        ctype = resp.headers.get("content-type", "")
        if resp.status_code != 200 or "application/json" in ctype:
            try:
                msg = resp.json()
            except Exception:
                msg = resp.text[:1000]
            raise RuntimeError(f"GPT-SoVITS /tts 调用失败 status={resp.status_code} body={msg}")
        return resp.content

    def _service_alive(self) -> bool:
        """轻量探活：能拿到任意 HTTP 响应即视为存活（包括 404）。
        GPT-SoVITS api_v2 在根路径返回 404 是正常的——它没有 / 路由。
        """
        try:
            r = requests.get(self.config.base_url + "/", timeout=3)
            return r.status_code < 600
        except Exception:
            return False

    @staticmethod
    def _make_silence_wav_bytes(seconds: float, sample_rate: int = 32000) -> bytes:
        """生成一段 mono / 16-bit / 32 kHz 静默 wav。
        32 kHz 是 GPT-SoVITS 默认采样率，便于和真实音频拼接时不报错。
        """
        n_frames = int(round(seconds * sample_rate))
        import io
        buf = io.BytesIO()
        with contextlib.closing(wave.open(buf, "wb")) as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            silence = struct.pack("<h", 0) * n_frames
            wf.writeframes(silence)
        return buf.getvalue()

    @staticmethod
    def _to_utf8_json(payload: dict[str, Any]) -> bytes:
        import json as _json
        return _json.dumps(payload, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def _get_wav_duration_seconds(audio_path: Path) -> float | None:
        try:
            with contextlib.closing(wave.open(str(audio_path), "rb")) as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate:
                    return round(frames / float(rate), 3)
        except Exception:
            return None
        return None


# --- 兼容旧 import 名（server.py 当前引用的是 CosyVoiceTTSService） ---
CosyVoiceTTSService = GPTSoVITSTTSService
