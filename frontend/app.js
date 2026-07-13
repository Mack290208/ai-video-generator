// AI 助教视频工坊 - Frontend App (清新教学风)
var segments = [];
var templates = {};
var settings = { quality: "medium", whisper: true, speed: 1.0, fontSize: 18, lang: "zh" };
var generating = false;
var chatMessages = [];
var llmProviders = [];
var currentProvider = null;

function API() { return document.getElementById("apiUrl") ? document.getElementById("apiUrl").value.replace(/\/+$/, "") : "http://127.0.0.1:8000"; }

var I18N = {
  zh: {
  "checking": "检测中...",
  "notConnected": "未连接",
  "connected": "已连接",
  "connFailed": "连接失败",
  "healthTTSDown": "TTS 服务未启动",
  "generating": "⏳ 生成中...",
  "genFailed": "生成失败",
  "sbSelectTpl": "选择模板...",
  "sbNarration": "旁白文本",
  "sbNarrPlaceholder": "这段的旁白内容...",
  "tplNone": "没有可用模板",
  "genReady": "就绪",
  "genProgress": "正在提交...",
  "genTTS": "TTS 合成中...",
  "genTTSComplete": "TTS 完成",
  "genResult": "✅ 生成完成",
  "genTTSDone": "TTS pipeline 完成！",
  "genTTSHint": "如需完整视频（含 Manim 动画），请在命令行运行：",
  "genNoSeg": "请先添加段落",
  "chatWelcome": "你好！我是 AI 助教，告诉我你想生成什么样的教学视频？",
  "chatNoApi": "LLM 接口待接入，当前仅 UI 演示",
  "settSaved": "设置已保存",
  "autoIODone": "已自动添加开场和结尾",
  "expDone": "JSON 已导出",
  "copied": "JSON 已复制"
},
  en: {
  "checking": "Checking...",
  "notConnected": "Disconnected",
  "connected": "Connected",
  "connFailed": "Connection failed",
  "healthTTSDown": "TTS service offline",
  "generating": "⏳ Generating...",
  "genFailed": "Generation failed",
  "sbSelectTpl": "Select template...",
  "sbNarration": "Narration",
  "sbNarrPlaceholder": "Narration text for this segment...",
  "tplNone": "No templates available",
  "genReady": "Ready",
  "genProgress": "Submitting...",
  "genTTS": "TTS synthesizing...",
  "genTTSComplete": "TTS Complete",
  "genResult": "✅ Generation Complete",
  "genTTSDone": "TTS pipeline complete!",
  "genTTSHint": "For full video (with Manim), run in terminal:",
  "genNoSeg": "Please add segments first",
  "chatWelcome": "Hi! I am the AI Teaching Assistant. What kind of video would you like to create?",
  "chatNoApi": "LLM API integration pending, UI demo only",
  "settSaved": "Settings saved",
  "autoIODone": "Auto-added intro and outro",
  "expDone": "JSON exported",
  "copied": "JSON copied"
}
};

function t(key) {
  var lang = settings.lang || "zh";
  return (I18N[lang] && I18N[lang][key]) || key;
}

function applyLang() {
  document.querySelectorAll("[data-i18n]").forEach(function(el) {
    var val = t(el.dataset.i18n);
    if (el.tagName === "INPUT" && el.type !== "button") el.placeholder = val;
    else if (el.tagName === "TEXTAREA") el.placeholder = val;
    else el.textContent = val;
  });
}

function toast(msg, type) {
  type = type || "info";
  var c = document.getElementById("toastContainer");
  var el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(function() { el.remove(); }, 4000);
}

// ==================== Navigation ====================
function goNav(name) {
  document.querySelectorAll(".nav-item").forEach(function(el) {
    el.classList.toggle("active", el.dataset.nav === name);
  });
  document.querySelectorAll(".page").forEach(function(el) {
    el.classList.toggle("active", el.id === "page-" + name);
  });
  // Update header steps
  var stepMap = { topic: "topic", edit: "edit", templates: "edit", generate: "generate", chat: "generate", settings: "generate" };
  var activeStep = stepMap[name] || "topic";
  document.querySelectorAll(".header-steps .step").forEach(function(el) {
    el.classList.toggle("active", el.dataset.step === activeStep);
  });
  if (name === "edit" || name === "generate") refreshPreview();
}

// ==================== Health ====================
async function checkHealth() {
  var dot = document.getElementById("statusDot");
  var txt = document.getElementById("statusText");
  
  try {
    var r = await fetch(API() + "/health", { signal: AbortSignal.timeout(5000) });
    var d = await r.json();
    var ttsUrl = d.tts_base_url || "http://127.0.0.1:9880";
    var ttsProvider = d.tts_provider || "gpt_sovits";
    
    // 检测 TTS 服务
    var ttsAlive = false;
    try {
      await fetch(ttsUrl + "/", { signal: AbortSignal.timeout(3000), mode: "no-cors" });
      ttsAlive = true;
    } catch (_) {}
    
    // 检测 LLM API
    var llmAlive = false;
    try {
      var llmResp = await fetch(API() + "/llm/providers", { signal: AbortSignal.timeout(3000) });
      if (llmResp.ok) {
        var llmData = await llmResp.json();
        llmAlive = llmData.providers && llmData.providers.length > 0;
      }
    } catch (_) {}
    
    // 更新状态显示
    if (ttsAlive && llmAlive) {
      dot.classList.add("online");
      txt.textContent = "✅ 全部就绪";
      txt.style.color = "#10b981";
    } else if (ttsAlive) {
      dot.classList.add("online");
      txt.textContent = "TTS ✓ / LLM ✗";
      txt.style.color = "#f59e0b";
    } else if (llmAlive) {
      dot.classList.remove("online");
      txt.textContent = "TTS ✗ / LLM ✓";
      txt.style.color = "#f59e0b";
    } else {
      dot.classList.remove("online");
      txt.textContent = "服务未就绪";
      txt.style.color = "#ef4444";
    }
    
    // 存储状态供其他地方使用
    window._healthStatus = { tts: ttsAlive, llm: llmAlive };
    
  } catch (e) {
    dot.classList.remove("online");
    txt.textContent = "连接失败";
    txt.style.color = "#ef4444";
    window._healthStatus = { tts: false, llm: false };
  }
}

// 定期检查健康状态
setInterval(checkHealth, 30000);  // 每 30 秒检查一次

// ==================== Templates ====================
async function loadTemplates() {
  try {
    var r = await fetch(API() + "/templates");
    var d = await r.json();
    templates = {};
    var list = d.templates || [];
    list.forEach(function(item) { templates[item.id] = item; });
    renderTemplates(list);
    toast(t("tplLoaded", list.length), "success");
  } catch (e) { toast("Failed: " + e.message, "error"); }
}

function renderTemplates(list) {
  var grid = document.getElementById("templatesGrid");
  if (!list.length) {
    grid.innerHTML = '<p class="empty-hint">' + t("tplNone") + '</p>';
    return;
  }
  grid.innerHTML = list.map(function(tpl) {
    var desc = tpl.summary || (tpl.meta && tpl.meta.summary) || "";
    return '<div class="template-card" onclick="selectTemplate(\'' + tpl.id + '\')">' +
      '<div class="name">' + tpl.id + '</div>' +
      '<div class="kind">' + (tpl.kind || "v2") + '</div>' +
      '<div class="desc">' + desc + '</div></div>';
  }).join("");
}

function selectTemplate(id) { toast("[" + id + "] selected", "info"); }

// ==================== Segments ====================
var TEMPLATE_OPTIONS = ["intro_v2","curve_descent","lr_comparison","bullet_summary","concept_compare","data_flow","formula_evolve","scatter_classify","gradient_descent","intro","outro"];

function addSegment(template, narration, params) {
  segments.push({ template: template || "", narration: narration || "", params: params || {} });
  renderSegments();
  updateEstimate();
}

function removeSegment(i) { segments.splice(i, 1); renderSegments(); updateEstimate(); }

function moveSegment(i, dir) {
  var j = i + dir;
  if (j < 0 || j >= segments.length) return;
  var tmp = segments[i]; segments[i] = segments[j]; segments[j] = tmp;
  renderSegments();
}

function updateSegment(i, field, value) {
  if (field === "template") segments[i].template = value;
  else if (field === "narration") segments[i].narration = value;
  else segments[i].params[field] = value;
  updateEstimate();
}

function renderSegments() {
  var c = document.getElementById("segmentsContainer");
  if (!segments.length) {
    c.innerHTML = '<p class="empty-hint">点击「选择主题」加载预设，或点击「添加段落」开始创作</p>';
    updatePreviewPanel();
    return;
  }
  var html = "";
  for (var i = 0; i < segments.length; i++) {
    var seg = segments[i];
    var opts = '<option value="">' + t("sbSelectTpl") + '</option>';
    for (var k = 0; k < TEMPLATE_OPTIONS.length; k++) {
      var tp = TEMPLATE_OPTIONS[k];
      opts += '<option value="' + tp + '"' + (seg.template === tp ? ' selected' : '') + '>' + tp + '</option>';
    }
    html += '<div class="segment-item">' +
      '<div class="seg-header"><div class="seg-header-left">' +
        '<div class="seg-num">' + (i+1) + '</div>' +
        '<select class="seg-template" onchange="updateSegment(' + i + ',\'template\',this.value)">' + opts + '</select>' +
        '<div class="move-btns">' +
          '<button onclick="moveSegment(' + i + ',-1)">↑</button>' +
          '<button onclick="moveSegment(' + i + ',1)">↓</button>' +
        '</div></div>' +
        '<button class="btn-remove" onclick="removeSegment(' + i + ')">✕</button></div>' +
      '<div class="seg-body">' +
        '<label>' + t("sbNarration") + '</label>' +
        '<textarea oninput="updateSegment(' + i + ',\'narration\',this.value)" placeholder="' + t("sbNarrPlaceholder") + '">' + (seg.narration || "") + '</textarea>' +
        '<div class="seg-params">' +
          '<div><label>title</label><input value="' + (seg.params.title||"") + '" oninput="updateSegment(' + i + ',\'title\',this.value)"></div>' +
          '<div><label>subtitle</label><input value="' + (seg.params.subtitle||"") + '" oninput="updateSegment(' + i + ',\'subtitle\',this.value)"></div>' +
          '<div><label>duration</label><input type="number" value="' + (seg.params.duration||5) + '" min="1" max="60" oninput="updateSegment(' + i + ',\'duration\',parseFloat(this.value))"></div>' +
        '</div></div></div>';
  }
  c.innerHTML = html;
  updateEstimate();
  updatePreviewPanel();
}

function autoIntroOutro() {
  var titleVal = document.getElementById("videoTitle").value || "AI 课堂";
  if (!segments.length || segments[0].template !== "intro_v2")
    segments.unshift({template:"intro_v2", narration: settings.lang==="en" ? "Welcome to today's lesson." : "大家好，欢迎来到今天的课程。", params:{title:titleVal, subtitle:"", duration:5}});
  if (segments.length < 2 || segments[segments.length-1].template !== "outro")
    segments.push({template:"outro", narration: settings.lang==="en" ? "That's all for today. See you next time!" : "好的，这就是今天的内容啦，我们下次再见！", params:{title: settings.lang==="en" ? "Summary" : "本节小结", duration:5}});
  renderSegments();
  toast(t("autoIODone"), "success");
}

// ==================== Estimate ====================
function estimateNarration(text) {
  var chars = (text.match(/[\u4e00-\u9fffA-Za-z0-9]/g) || []).length;
  var pauses = (text.match(/[。？！?!,，、；;,\.]/g) || []).reduce(function(s,c) {
    return s + ("。？！?!.".indexOf(c) >= 0 ? 0.4 : 0.2);
  }, 0);
  return Math.max(1.5, chars / 5.5 + pauses);
}

function updateEstimate() {
  var total = segments.reduce(function(s, seg) { return s + estimateNarration(seg.narration || ""); }, 0);
  document.getElementById("estDuration").textContent = total.toFixed(1) + "s";
  document.getElementById("segCount").textContent = segments.length;
}

function updatePreviewPanel() {
  var titleEl = document.getElementById("previewTitle");
  if (titleEl) titleEl.textContent = document.getElementById("videoTitle").value || "未设置";
  var container = document.getElementById("previewSegments");
  if (!container) return;
  if (!segments.length) {
    container.innerHTML = '<div class="preview-empty">暂无段落</div>';
    return;
  }
  container.innerHTML = segments.map(function(seg, i) {
    var name = seg.template || seg.narration.substring(0, 12) || "...";
    return '<div class="preview-seg-item"><div class="preview-seg-num">' + (i+1) + '</div><div class="preview-seg-name">' + name + '</div></div>';
  }).join("");
}

// ==================== Storyboard JSON ====================
function buildStoryboard() {
  return {
    video_title: document.getElementById("videoTitle").value || "Untitled",
    duration_target_seconds: parseFloat(document.getElementById("durationTarget").value) || null,
    segments: segments.map(function(seg) {
      return {
        kind: seg.template || "bullet_summary",
        template: seg.template || "bullet_summary",
        narration: seg.narration || "",
        subtitle: seg.narration || "",
        params: Object.assign({ duration: 5 }, seg.params || {})
      };
    })
  };
}

function refreshPreview() {
  document.getElementById("jsonPreview").value = JSON.stringify(buildStoryboard(), null, 2);
}

function copyJSON() {
  refreshPreview();
  navigator.clipboard.writeText(document.getElementById("jsonPreview").value);
  toast(t("copied"), "success");
}

function exportJSON() {
  refreshPreview();
  var b = new Blob([document.getElementById("jsonPreview").value], { type: "application/json" });
  var a = document.createElement("a");
  a.href = URL.createObjectURL(b);
  a.download = "storyboard.json";
  a.click();
  toast(t("expDone"), "success");
}

function importJSON() {
  var inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json";
  inp.onchange = async function(e) {
    var f = e.target.files[0]; if (!f) return;
    try {
      var sb = JSON.parse(await f.text());
      document.getElementById("videoTitle").value = sb.video_title || "";
      document.getElementById("durationTarget").value = sb.duration_target_seconds || 60;
      segments = (sb.segments || []).map(function(s) {
        return { template: s.template || s.kind || "", narration: s.narration || "", params: s.params || {} };
      });
      renderSegments();
      goNav("edit");
      toast(t("impDone", segments.length), "success");
    } catch(err) { toast(t("impFail", String(err)), "error"); }
  };
  inp.click();
}

// ==================== Presets ====================
var PRESETS = {
  "decisionTree": {
    "video_title": "决策树详解",
    "duration_target_seconds": 60,
    "segments": [
      {
        "kind": "intro_v2",
        "template": "intro_v2",
        "narration": "大家好，欢迎来到今天的课程。今天我们将一起学习决策树。",
        "subtitle": "",
        "params": {
          "title": "决策树详解",
          "duration": 5
        }
      },
      {
        "kind": "bullet_summary",
        "template": "bullet_summary",
        "narration": "决策树是一种常见的监督学习算法。它的核心思想是通过一系列条件判断，将数据逐步细分，最终得到分类结果。",
        "subtitle": "",
        "params": {
          "title": "什么是决策树",
          "duration": 8
        }
      },
      {
        "kind": "concept_compare",
        "template": "concept_compare",
        "narration": "在选择分裂特征时，常用两种方法。信息增益倾向于选择取值多的特征，而基尼系数则更加稳健，计算也更快。",
        "subtitle": "",
        "params": {
          "title": "信息增益 vs 基尼系数",
          "duration": 8
        }
      },
      {
        "kind": "bullet_summary",
        "template": "bullet_summary",
        "narration": "决策树的优点是可解释性强、不需要太多数据预处理。缺点是容易过拟合，对噪声数据敏感。",
        "subtitle": "",
        "params": {
          "title": "优缺点",
          "duration": 7
        }
      },
      {
        "kind": "outro",
        "template": "outro",
        "narration": "好的，这就是今天的内容啦，我们下次再见！",
        "subtitle": "",
        "params": {
          "title": "本节小结",
          "duration": 5
        }
      }
    ]
  },
  "gradientDescent": {
    "video_title": "梯度下降",
    "duration_target_seconds": 60,
    "segments": [
      {
        "kind": "intro_v2",
        "template": "intro_v2",
        "narration": "大家好，今天我们来学习梯度下降算法。",
        "subtitle": "",
        "params": {
          "title": "梯度下降",
          "duration": 5
        }
      },
      {
        "kind": "curve_descent",
        "template": "curve_descent",
        "narration": "梯度下降是优化算法的核心。想象你蒙着眼睛站在山上，要找到最低点，你只能感受脚下的坡度，沿着最陡的方向往下走。",
        "subtitle": "",
        "params": {
          "title": "直观理解",
          "duration": 10
        }
      },
      {
        "kind": "lr_comparison",
        "template": "lr_comparison",
        "narration": "学习率决定了每一步走多大学习率太大会震荡，太小则收敛很慢。选择合适的学习率非常重要。",
        "subtitle": "",
        "params": {
          "title": "学习率的影响",
          "duration": 8
        }
      },
      {
        "kind": "bullet_summary",
        "template": "bullet_summary",
        "narration": "常见的变体有批量梯度下降、随机梯度下降和小批量梯度下降。实际深度学习中最常用的是Adam优化器。",
        "subtitle": "",
        "params": {
          "title": "常见变体",
          "duration": 7
        }
      },
      {
        "kind": "outro",
        "template": "outro",
        "narration": "好的，这就是今天的内容啦，我们下次再见！",
        "subtitle": "",
        "params": {
          "title": "本节小结",
          "duration": 5
        }
      }
    ]
  },
  "supervised": {
    "video_title": "监督学习入门",
    "duration_target_seconds": 60,
    "segments": [
      {
        "kind": "intro_v2",
        "template": "intro_v2",
        "narration": "大家好，今天我们来聊一聊监督学习。",
        "subtitle": "",
        "params": {
          "title": "监督学习入门",
          "duration": 5
        }
      },
      {
        "kind": "bullet_summary",
        "template": "bullet_summary",
        "narration": "监督学习是最常见的机器学习范式。简单来说，就是从带标签的数据中学习输入到输出的映射关系。",
        "subtitle": "",
        "params": {
          "title": "什么是监督学习",
          "duration": 8
        }
      },
      {
        "kind": "scatter_classify",
        "template": "scatter_classify",
        "narration": "比如我们有一堆标注了猫和狗的图片，模型通过学习这些样本，就能对新的图片做出判断。",
        "subtitle": "",
        "params": {
          "title": "分类任务示例",
          "duration": 8
        }
      },
      {
        "kind": "concept_compare",
        "template": "concept_compare",
        "narration": "监督学习主要分为分类和回归两大类。分类预测离散类别，回归预测连续数值。",
        "subtitle": "",
        "params": {
          "title": "分类 vs 回归",
          "duration": 6
        }
      },
      {
        "kind": "outro",
        "template": "outro",
        "narration": "好的，这就是今天的内容啦，我们下次再见！",
        "subtitle": "",
        "params": {
          "title": "本节小结",
          "duration": 5
        }
      }
    ]
  }
};

function loadPreset(name) {
  var preset = PRESETS[name];
  if (!preset) { toast("Unknown preset: " + name, "error"); return; }
  document.getElementById("videoTitle").value = preset.video_title || "";
  document.getElementById("durationTarget").value = preset.duration_target_seconds || 60;
  segments = (preset.segments || []).map(function(s) {
    return { template: s.template || s.kind || "", narration: s.narration || "", params: s.params || {} };
  });
  renderSegments();
  goNav("edit");
  toast("已加载「" + name + "」预设", "success");
}

// ==================== Generate Video ====================
async function generateVideo() {
  if (generating) return;
  if (!segments.length) { 
    toast(t("genNoSeg"), "error"); 
    // 显示友好的提示
    var logBox = document.getElementById("logBox");
    logBox.innerHTML = '<div class="warning-message">请先添加段落：点击「选择主题」加载预设，或点击「添加段落」开始创作</div>';
    return; 
  }

  generating = true;
  refreshPreview();
  var sb = buildStoryboard();
  var btn = document.getElementById("btnGenerate");
  btn.disabled = true;
  btn.classList.add("btn-loading");
  btn.innerHTML = '<span class="loading-spinner"></span> 生成中...';

  var logBox = document.getElementById("logBox");
  logBox.innerHTML = "";
  var progressFill = document.getElementById("progressFill");
  var progressText = document.getElementById("progressText");
  
  // 隐藏之前的结果
  document.getElementById("resultBox").style.display = "none";
  document.getElementById("previewContainer").style.display = "none";
  
  progressFill.style.width = "5%";
  progressText.textContent = "准备中...";

  function appendLog(msg, type) {
    type = type || "info";
    var div = document.createElement("div");
    div.className = type + "-message";
    div.textContent = msg;
    logBox.appendChild(div);
    logBox.scrollTop = logBox.scrollHeight;
  }

  try {
    appendLog("正在提交 storyboard...", "info");
    progressFill.style.width = "10%";
    progressText.textContent = "TTS 语音合成中...";

    var response = await fetch(API() + "/tts/pipeline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sb)
    });

    if (!response.ok) {
      var errText = await response.text();
      var errMsg = "";
      try {
        var errJson = JSON.parse(errText);
        errMsg = errJson.detail || errJson.message || errText;
      } catch(e) {
        errMsg = errText;
      }
      throw new Error(errMsg);
    }

    var result = await response.json();
    
    // 检查是否有错误
    if (result.error) {
      throw new Error(result.error);
    }
    
    appendLog("视频生成完成！", "success");

    // 显示结果
    var resultBox = document.getElementById("resultBox");
    var resultContent = document.getElementById("resultContent");
    resultBox.style.display = "block";

    var html = "";
    if (result.segments_count) html += '<div class="result-item"><span>视频段数:</span><span>' + result.segments_count + '</span></div>';
    if (result.total_duration) html += '<div class="result-item"><span>总时长:</span><span>' + result.total_duration.toFixed(1) + 's</span></div>';
    if (result.file_size_bytes) html += '<div class="result-item"><span>文件大小:</span><span>' + (result.file_size_bytes / 1024 / 1024).toFixed(1) + 'MB</span></div>';
    resultContent.innerHTML = html;

    // 预览视频
    if (result.output_video) {
      var previewContainer = document.getElementById("previewContainer");
      var previewVideo = document.getElementById("previewVideo");
      if (previewContainer && previewVideo) {
        previewContainer.style.display = "block";
        var videoUrl = API() + "/outputs/video/" + result.output_video;
        appendLog("视频地址: " + result.output_video, "info");
        previewVideo.src = videoUrl;
        previewVideo.load();
        
        // 自动滚动到视频预览
        previewContainer.scrollIntoView({ behavior: "smooth" });
      }
    }

    progressFill.style.width = "100%";
    progressText.textContent = "✅ 生成完成！";
    toast("视频生成成功！", "success");

  } catch (e) {
    appendLog("错误: " + e.message, "error");
    progressText.textContent = "❌ 生成失败";
    progressFill.style.width = "0%";
    toast("生成失败: " + e.message, "error");
  } finally {
    generating = false;
    btn.disabled = false;
    btn.classList.remove("btn-loading");
    btn.innerHTML = "🎬 开始生成";
  }
}

// ==================== Chat ====================
function addChatMessage(role, text) {
  var box = document.getElementById("chatBox");
  var div = document.createElement("div");
  div.className = "chat-msg " + role;
  var bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = text;
  div.appendChild(bubble);
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

// 加载 LLM 提供商列表
async function loadLLMProviders() {
  try {
    var resp = await fetch(API() + "/llm/providers");
    if (resp.ok) {
      var data = await resp.json();
      llmProviders = data.providers || [];
      updateModelSelect();
    }
  } catch (e) {
    console.error("加载 LLM 提供商失败:", e);
  }
}

// 更新模型选择下拉框
function updateModelSelect() {
  var select = document.getElementById("modelSelect");
  if (!select) return;
  
  select.innerHTML = "";
  
  if (llmProviders.length === 0) {
    select.innerHTML = "<option value=\"\">未配置 LLM API</option>";
    document.getElementById("modelStatus").textContent = "请配置 .env 文件";
    return;
  }
  
  llmProviders.forEach(function(provider, index) {
    var option = document.createElement("option");
    option.value = provider.id;
    option.textContent = provider.name + " (" + provider.model + ")";
    if (index === 0) option.selected = true;
    select.appendChild(option);
  });
  
  currentProvider = llmProviders[0].id;
  document.getElementById("modelStatus").textContent = "已连接";
}

// 模型选择变化
function onModelChange(providerId) {
  currentProvider = providerId;
  var provider = llmProviders.find(function(p) { return p.id === providerId; });
  if (provider) {
    document.getElementById("modelStatus").textContent = "已选择: " + provider.name;
  }
}

async function sendChat() {
  var input = document.getElementById("chatInput");
  var text = input.value.trim();
  if (!text) return;
  input.value = "";
  addChatMessage("user", text);
  chatMessages.push({ role: "user", content: text });

  var box = document.getElementById("chatBox");
  var typingDiv = document.createElement("div");
  typingDiv.className = "chat-msg bot";
  typingDiv.id = "typingIndicator";
  var typingBubble = document.createElement("div");
  typingBubble.className = "chat-bubble";
  typingBubble.innerHTML = '<span class="loading-spinner"></span> 正在思考...';
  typingDiv.appendChild(typingBubble);
  box.appendChild(typingDiv);
  box.scrollTop = box.scrollHeight;

  // 禁用发送按钮
  var sendBtn = document.querySelector('.chat-input-bar .btn');
  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="loading-spinner"></span> 思考中';
  }

  try {
    var resp = await fetch(API() + "/chat/generate-storyboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: chatMessages, provider: currentProvider })
    });

    var indicator = document.getElementById("typingIndicator");
    if (indicator) indicator.remove();

    if (resp.ok) {
      var data = await resp.json();
      
      // 显示 AI 回复
      addChatMessage("bot", data.message || "收到");
      
      // 将 AI 回复添加到历史
      chatMessages.push({ role: "assistant", content: data.message || "收到" });

      // 如果生成了 storyboard
      if (data.storyboard && data.should_generate) {
        // 填充 segments
        segments = [];
        var segs = data.storyboard.segments || [];
        segs.forEach(function(seg) {
          addSegment(seg.template, seg.narration, seg.params || {});
        });
        renderSegments();
        updateEstimate();

        // 切换到编辑页面
        goNav("edit");
        toast("已生成 " + segs.length + " 个段落", "success");
      }
    } else {
      var err = await resp.text();
      addChatMessage("bot", "出错了: " + err);
    }
  } catch (e) {
    var indicator = document.getElementById("typingIndicator");
    if (indicator) indicator.remove();
    addChatMessage("bot", "请求失败: " + e.message);
  } finally {
    // 恢复发送按钮
    var sendBtn = document.querySelector('.chat-input-bar .btn');
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.textContent = "发送";
    }
  }
}

// 快速生成 storyboard
async function quickGenerate() {
  var input = document.getElementById("chatInput");
  var text = input.value.trim();
  if (!text) {
    toast("请输入视频主题", "error");
    return;
  }
  
  // 添加明确的生成指令
  input.value = "";
  var generateMsg = "帮我生成关于「" + text + "」的教学视频 storyboard";
  addChatMessage("user", generateMsg);
  chatMessages.push({ role: "user", content: generateMsg });
  
  // 调用 sendChat
  await sendChat();
}

// ==================== Settings ====================
function switchLang(lang) {
  settings.lang = lang;
  document.getElementById("settLang").value = lang;
  document.getElementById("langSwitch").value = lang;
  applyLang();
  renderSegments();
}

function saveSettings() {
  settings.quality = document.getElementById("settQuality").value;
  settings.whisper = document.getElementById("settWhisper").value === "true";
  settings.speed = parseFloat(document.getElementById("settSpeed").value) || 1.0;
  settings.fontSize = parseInt(document.getElementById("settFontSize").value) || 18;
  settings.lang = document.getElementById("settLang").value;
  localStorage.setItem("ai_video_gen_settings", JSON.stringify(settings));
  applyLang();
  renderSegments();
  toast(t("settSaved"), "success");
}

function loadSettings() {
  try {
    var saved = localStorage.getItem("ai_video_gen_settings");
    if (saved) Object.assign(settings, JSON.parse(saved));
  } catch(e) {}
  var q = document.getElementById("settQuality");
  var w = document.getElementById("settWhisper");
  var s = document.getElementById("settSpeed");
  var f = document.getElementById("settFontSize");
  var l = document.getElementById("settLang");
  var ls = document.getElementById("langSwitch");
  if (q) q.value = settings.quality;
  if (w) w.value = settings.whisper ? "true" : "false";
  if (s) s.value = settings.speed;
  if (f) f.value = settings.fontSize;
  if (l) l.value = settings.lang;
  if (ls) ls.value = settings.lang;
}

// ==================== Init ====================
document.addEventListener("DOMContentLoaded", function() {
  loadSettings();
  applyLang();
  renderSegments();
  checkHealth();
  loadLLMProviders();  // 加载 LLM 提供商列表

  // Chat Enter key
  var chatInput = document.getElementById("chatInput");
  if (chatInput) {
    chatInput.addEventListener("keydown", function(e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
    });
  }

  // Header step clicks
  document.querySelectorAll(".header-steps .step").forEach(function(el) {
    el.addEventListener("click", function() {
      var step = el.dataset.step;
      if (step === "topic") goNav("topic");
      else if (step === "edit") goNav("edit");
      else if (step === "generate") goNav("generate");
    });
  });

  // Video title sync to preview
  var titleInput = document.getElementById("videoTitle");
  if (titleInput) {
    titleInput.addEventListener("input", function() {
      var pt = document.getElementById("previewTitle");
      if (pt) pt.textContent = titleInput.value || "未设置";
    });
  }
});
