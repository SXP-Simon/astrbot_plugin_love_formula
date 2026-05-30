<div align="center">

# 💖 Love Formula: 赛博恋爱演化诊断插件

[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-ff69b4?style=for-the-badge)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/License-AGPL3.0-green.svg?style=for-the-badge)](LICENSE)
[![](https://img.shields.io/badge/五彩斑斓的Bug群-Bug反馈群&水群-white?style=for-the-badge&color=76bad9&logo=qq&logoColor=76bad9)](https://qm.qq.com/q/oTzIrdDBIc)

_✨ “假如这个群是你的恋人，你今天的表现是顶级偶像还是败犬 NPC？”✨_

<img src="https://count.getloli.com/@astrbot_plugin_love_formula?name=astrbot_plugin_love_formula&theme=booru-jaypee&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto" alt="count" />
</div>

本插件基于“恋爱动力学”逻辑，通过分析群成员每日的社交行为数据，利用大语言模型生成一份极具“二次元/亚文化”色彩的恋爱成分诊断报告。


---

## ⌨️ 交互指令
- `/今日人设`: 立即生成并渲染你的赛博恋爱诊断报告。
- `/今日人设 @用户`: 审判特定成员的社交表现。
- `/学习`: 指定回复一条消息，让插件记录该消息往后的所有消息，避免刚刚安装插件没有数据的冷启动问题。

---

## 🎨 视觉风格 (Galgame UI)
提供精致的报表渲染，包含：
- **群聊好感度**: 综合评价你今日的社交能量。
- **四维指标网格**: 展示“纯爱值”、“存在感”、“败犬值”与“白月光指数”。
- **AI 毒舌点评**: 极度中二、辛辣且精准的亚文化行为诊断。
- **灵魂回响 (Deep Dive)**: 深度解析最近消息片段，挖掘你的潜台词与真实心理。
- **呈堂证供**: 自动提取并复现聊天现场，让 AI 的诊断有据可依。

---

![galgame-demo](./assets/themes/galgame/galgame-demo.jpg)

---

## 📊 核心指标映射 (Terminology)

我们抛弃了枯燥的统计学术语，全面拥抱亚文化梗语境：

| 维度 | ACG/潮流称呼 | **💕 赛博恋爱映射** | **📈 计算逻辑** |
| :--- | :--- | :--- | :--- |
| **Simp ($S$)** | **纯爱值** | **付出与投射**：代表你的主动交互频率。 | 发言数、戳一戳、文字长度。 |
| **Vibe ($V$)** | **存在感** | **吸引力光环**：代表他人对你的正向反馈。 | 被回复数、被表态/贴贴数。 |
| **Ick ($I$)** | **败犬值** | **社交尴尬度**：社交失误或破坏氛围。 | **撤回消息**、刷屏、语无伦次。 |
| **Nostalgia ($N$)** | **白月光指数** | **情感积淀**：人际关系的厚度与破冰力。 | **昨日好感度**、开启新话题次数。 |

> [!TIP]
> **白月光逻辑**：今日的 `Nostalgia` = 昨日最终好感度 + 今日破冰表现。这让你的情圣（或败犬）属性具有了跨周期的连续性。

---

## 🎭 角色人设 (Archetypes)

根据各项指标的权重均衡，你会被判定为以下几种人设：
- **纯爱战神 (反讽)**: 高投入、低回报的深情（卑微）代表。
- **现充达人**: 极低投入却随处散发魅力的社交掌控者。
- **白月光/顶级偶像**: 群内的核心，几乎不主动但深受宠爱，且有历史好感层层堆叠。
- **遗憾败犬**: 魅力虽高，但因频繁撤回或犹豫不决导致“败犬气息”浓郁。
- **背景板 NPC**: 处于潜水边缘，社交存在感极低的过路人。

---

## 🛠️ 安装与配置

本项目支持高度自定义，可通过 `_conf_schema.json` 或管理后台配置：

1. **权限控制**：
   - `group_list_mode`: 支持 `whitelist` (白名单) 或 `blacklist` (黑名单)。
   - `group_list`: 设置对应的群号列表。

2. **模型适配**：
   - `commentary_provider_id`: 专用于生成“毒舌点评”的模型（推荐轻量级模型）。
   - `deep_dive_provider_id`: 专用于深度侧写的模型（推荐高智力模型）。

3. **阈值设定**：
   - `min_msg_threshold`: 触发诊断的最小发言数 (默认 3 条)。
   - `analyze_history_count`: 深度侧写读取的消息条数（建议 20-50 条）。

---

## 🧪 测试与产物治理

轻量验证脚本、示例卡片渲染方式，以及运行时数据库/生成产物的提交规则见 [docs/testing.md](docs/testing.md)。提交新的 fixture、snapshot 或文档资产前，请先确认其中不包含真实群聊或用户隐私数据。

---

## 🔗 关于
- **Author**: SXP-Simon
- **Repository**: [GitHub](https://github.com/SXP-Simon/astrbot_plugin_love_formula)

> **注意**：本插件数据仅供娱乐，请勿因“败犬值”过高而产生焦虑。保持真实的社交节奏，毕竟——每一条消息都是一次调情。 😉
