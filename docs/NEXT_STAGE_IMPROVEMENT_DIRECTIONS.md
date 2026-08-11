# 下一阶段改进方向

## 文档定位

本文是 `v0.2-demo` 之后下一阶段改进方向的讨论稿，用于梳理项目为什么需要继续提升、三个主要方向之间是什么关系、各方向希望解决什么问题，以及什么状态可以认为方向已经基本成熟。

本文不是执行计划，也不是第一阶段单体 build plan 的延续。它为 [Phase A–E](tickets/README.md) 提供方向背景，但不能替代具体 ticket。本文当前不规定：

- 具体代码改动；
- 可直接执行的 ticket、执行 prompt 或 Allowed Files；
- 最终 State Schema 字段；
- 最终节点名称和全部 conditional edge；
- 具体 RAG 框架、向量数据库或 PDF 解析工具；
- 具体开发日期、工作量和提交顺序；
- 尚未经过讨论的实现细节。

后续应通过 `docs/tickets/` 逐项完成设计讨论，再把已经确认的结论同步到核心文档；只有用户确认并标记为 `status: ready` 的具体 ticket 才能执行。

截至 2026-08-11，A01 已确认目标 transition contract；A02 corrective implementation 已完成 formal Run、current-route transition allocation、canonical Attempt kinds 和 Human identity 验收。A02 的四层 fallback coverage 仍是 protocol harness，不表示产品 graph 已开放这些路线。

## 当前阶段判断

项目当前已经完成 `v0.2-demo` 里程碑。它已经不是只有空节点的 LangGraph skeleton，而是一个能够演示的科研工作流 MVP：

- 主流程中的 Method Planner、Codex Handoff、Analysis Engineer、Scientific Reviewer、Decision Coordinator、Human Approval Gate、Memory and Report 已经完成基本接线；
- 确定性分析、科学诊断、安全下限、artifact contract、checkpoint、synthetic benchmark 和 live provider 演示已经具备；
- good、ambiguous、bad 类型的 synthetic cases 已经能够验证部分重要行为；
- Golden Demo 可以展示高风险结果如何被阻止进入 accepted memory；
- 当前版本适合作为下一阶段之前的稳定演示基线。

但是，目前的成熟主要是“单轮、受控、可演示”的成熟，还不是“可长期循环、自主修复、可并行扩展”的成熟。下一阶段需要解决的是系统可靠性和能力上限，而不是继续堆叠更多表面功能。

当前主要缺口可以概括为：

1. 图中声明的路线、真实可执行的路线和测试覆盖的路线还没有完全统一；
2. current routes 已有可审计的 Attempt/Transition protocol，但 rerun、code fix、replan 等 A01 回退尚未接成完整产品循环；
3. Codex Handoff 虽然位于图中，但真正的编码智能仍主要由图外的 Codex CLI worker 提供；
4. Agent 已经具有结构化职责，但物理知识、工具能力和基于证据的判断能力仍可继续加强；
5. 当前 harness 能证明主要 demo 可用，但还不能系统证明所有允许的边、循环、恢复和未来并行行为都可靠。

## 下一阶段总体目标

下一阶段不是简单增加更多 Agent，而是把当前系统提升为一个具有以下特征的科研多 Agent 工作流：

- **流程可靠**：每条允许路线都有明确条件、状态变化、停止条件和测试证据；
- **循环可审计**：每次 replan、code fix、rerun 都产生新的 attempt，不覆盖或混淆旧结果；
- **执行可恢复**：Human Gate、失败节点和长任务能够从 checkpoint 继续，而不是重新伪装成一次全新运行；
- **编码能力图内受控**：Code Agent 由 LangGraph 管理输入、权限、预算和结果，但代码执行仍处于隔离环境；
- **物理能力有证据来源**：Agent 可以使用经过管理的物理知识和运行证据，而不是依赖无来源的自由生成；
- **提升可度量**：图、Agent、RAG、Prompt 或模型升级后，都能通过分层 harness 判断是否真正改善；
- **科研边界不后退**：能力增强不能绕过确定性诊断、安全下限、provenance 和 Human Approval Gate。

## 总体设计原则

### 1. 控制能力与智能能力分离

路由、attempt、预算、checkpoint、artifact invalidation 和审批属于控制层；LLM 推理、代码修改、RAG 和物理判断属于能力层。

能力层可以逐步更换模型、Prompt、工具或检索系统，但不应改变控制层的安全规则。控制层也必须能够使用 Fake Agent 独立验证，不依赖真实 LLM 恰好输出正确结果。

### 2. 先定义契约，再替换真实能力

图的修复不能完全忽略未来 Code Agent，但也不需要等待完整 Code Agent 实现。应先定义 Code Agent 的输入、输出和失败类型，再用确定性 Fake Code Agent 验证控制流程，最后接入真实实现。

同样，RAG 也不应先接入所有 Agent。应先定义 evidence bundle、citation、来源版本和“不知道”的表达方式，再决定检索实现。

### 3. 逻辑可以回退，历史不能倒退

Decision Coordinator 可以根据 A01 合同派发 re-review、analysis rerun、code fix 或 replan，但旧的 plan、analysis、review 和 decision 不应被静默覆盖。Worker Agent 和 Human Gate 都不能绕过 Coordinator 直接控制 graph-level 回退。

每次循环都应被理解为从已有证据派生出的新 attempt，而不是对旧 run directory 进行原地重写。

### 4. 确定性规则优先于 LLM 判断

可以由确定性代码判断的问题，应继续使用 schema validation、数值诊断、allowlist、risk floor 和 artifact checks。LLM 主要处理语义理解、方案生成、证据组织和复杂建议，不应取代可以重复验证的科学或安全规则。

### 5. 不把“更多自治”误认为“更强能力”

Agent 变强不等于允许它跳转到更多节点或获得更多写权限。能力增强需要与更严格的证据、预算、验证和失败边界同步。

## 方向一：图、状态与 Harness 的可靠性升级

### 方向目标

把当前“主要路径可运行”的图提升为“所有允许路径都被定义、可恢复、可测试、可解释”的控制系统。

这个方向是下一阶段的基础，因为 Code Agent 和 RAG 都会增加非确定性。如果循环、状态和产物规则没有先稳定，后续很难判断问题来自 Agent 能力，还是来自图本身。

### 当前要解决的核心问题

- 图中存在一些已经画出或记录的回退方向，但当前 routing function 并不会真正选择它们；
- Coordinator 的 rerun 或 code-fix 建议与实际 graph transition 尚未完全统一；
- Human Approval Gate 的 rerun 决定当前更多是记录意图，而不是真正恢复到下一轮 Analysis；
- A02 已在 state 和 append-only ledger 中表达 current Run/Cycle/Attempt/Transition/Human identity 与 control lineage，但 domain artifact 仍使用当前 fixed paths；
- 不同层级的旧产物在回退后应该如何失效，尚未成为明确合同；
- checkpoint 已经存在，但 runner 的启动、暂停和恢复协议仍需重新梳理；
- 当前没有真实 fan-out，因此暂时没有并行冲突，但未来加入并行 Reviewer 或诊断节点后会出现共享 state merge 问题；
- 测试覆盖了许多节点和主要路径，但还没有形成完整的 edge、trajectory、cycle 和 recovery coverage。

### 需要形成的控制模型

#### 1. 允许路线矩阵

需要明确区分：

- 图上技术上可以连接的边；
- 产品上允许出现的边；
- 当前版本已经实现的边；
- harness 已经验证的边。

每条允许路线至少需要回答：

- 谁提出跳转；
- 哪个确定性条件允许跳转；
- 需要哪些前置 artifacts；
- 哪些旧 artifacts 失效；
- 是否创建新 attempt；
- 重试或循环预算如何变化；
- 下一节点完成后如何重新进入主流程；
- 什么条件必须进入 Human Gate 或停止。

最终不应出现“图上画了，但 routing 永远不会选择”或者“Agent 提出了 rerun，但 runner 只能结束”的长期不一致。

#### 2. Run、Cycle 与 Attempt 的层次

A02 已固定三种概念：

- **Run**：用户发起的一次完整科研任务；
- **Cycle**：同一方法合同下的 execution epoch，只在 initial 或 replan 创建；
- **Attempt**：一次产生持久状态、artifact 或决策的 graph node invocation。

它们已经成为 current control-plane schema，并能够表达：

- 当前执行属于哪一轮；
- 为什么产生新一轮；
- 它继承了哪些输入；
- 哪个 source Attempt、Transition 或 Human decision 触发了它；
- 相关 input/output/evidence references。

哪些旧结果失效仍由 A03 定义；是否达到循环预算以及如何识别重复失败仍由 A06 定义。A02 identity 不能被解释成这两个合同已经存在。

当前 product routes 已使用 Transition commit 在目标副作用前预分配 Attempt；Run、Cycle、Attempt、Transition、Human Request 和 Human Response lifecycle 写入 `execution_history.jsonl`。re-review、analysis rerun、code fix 和 replan 目前只经过 A02 最小 identity harness，尚不能据此宣称完整循环已实现。A03 继续决定 artifact invalidation，A04 决定 durable resume/replay/fork，A06 决定预算。

#### 3. Artifact Invalidation 规则

回退不是简单修改 `current_node`。不同回退目标应有不同失效范围。初步方向是：

| 回退目标 | 原则上的失效范围 |
| --- | --- |
| Reviewer | 旧 review 和 decision 失效，analysis 结果可以继续使用 |
| Analysis Engineer | 旧 analysis、review 和 decision 失效，已批准的 plan 可以继续使用 |
| Code Agent | 旧 code attempt 及其下游 analysis、review、decision 失效 |
| Method Planner | 旧 plan 及全部下游结果失效 |

这里的“失效”应表示不再作为当前结果，而不是删除历史文件。最终规则仍需结合 artifact 目录设计进一步讨论。

#### 4. Durable Pause and Resume

Human Approval Gate、等待代码修改、外部长任务和可恢复错误，应逐步从“写 pending artifact 后结束”提升为真正的 pause/resume 语义。

需要明确：

- 哪些状态是暂停，哪些状态是终止；
- 谁拥有恢复权限；
- 恢复时是否沿用同一个 checkpoint thread；
- 恢复输入如何验证；
- interrupt 之前的副作用如何保持幂等；
- runner 如何区分 start、resume、replay 和 fork。

#### 5. Budget 与停止条件

所有循环都必须是有限的。未来至少需要统一考虑：

- code attempt 上限；
- analysis rerun 上限；
- replan 上限；
- 总 graph cycle 上限；
- LLM token 或调用预算；
- wall-clock timeout；
- 连续相同失败的停止条件；
- 必须升级到 Human Gate 的条件。

预算不只是成本控制，也是防止 Agent 在没有新证据时反复循环的科学和工程边界。

#### 6. 并行与 State Merge

下一阶段不以“尽可能并行”为目标。只有真正独立、可合并的工作才适合并行，例如不同类型的科学诊断或多个只读证据检索。

未来并行设计应遵循：

- 并行节点写入不同的 state key 或带来源标识的结果；
- 共享列表或集合有明确 reducer；
- 需要最终决定的内容由 join node 统一生成；
- 并行结果的顺序不被当作科学含义；
- 有副作用的控制节点默认保持串行；
- harness 必须验证部分分支失败、恢复和重复执行时的行为。

### Harness 的目标结构

Harness 应逐步形成相互分离但可以组合的层次：

1. **Schema and invariant tests**：验证状态、artifact、风险下限和不变量；
2. **Node tests**：使用确定性输入单独验证每个节点；
3. **Route tests**：验证每个 routing condition 和允许目标；
4. **Partial-path tests**：从构造好的 checkpoint/state 只运行图的一部分；
5. **Trajectory tests**：验证节点访问顺序、必经节点和禁止路径；
6. **Cycle tests**：至少覆盖成功回环、失败回环、预算耗尽和 Human Gate；
7. **Failure-injection tests**：模拟工具失败、坏 artifact、超时、重复失败和恢复；
8. **Parallel-merge tests**：未来出现 fan-out 后验证 reducer 和 join；
9. **Live-provider evaluations**：验证真实 LLM 下的语义质量和路线稳定性；
10. **Regression benchmark**：比较不同模型、Prompt、Agent 能力和 RAG 版本。

确定性路径应使用严格断言；可能存在多条合理路线的 Agent 行为应使用必经节点、禁止节点、subset/superset 或基于 rubric 的评估，不应把所有真实 LLM 行为强制成唯一字符串输出。

### 本方向达到阶段性成熟的标志

- 每条允许路线都有定义、实现和至少一项 harness 证据；
- 不允许的跳转无法由自由文本触发；
- rerun、code fix、replan 都会产生可审计的新 attempt；
- 回退后的旧 artifact 不会被误认为当前结果；
- Human Gate 能够在同一执行上下文中安全恢复；
- 循环达到预算时能够明确停止或升级；
- checkpoint history 可以解释一次运行为什么到达当前状态；
- 未来并行节点不会竞争写入没有 reducer 的共享字段；
- graph coverage 报告能够显示仍未验证的边和循环。

### 后续需要讨论的问题

- artifact namespace 的具体目录结构；
- 哪些状态进入 checkpoint，哪些只存在 artifact；
- A01 transition matrix 如何编码进产品 graph 与 coverage report；
- Human Gate 的 start/resume CLI 或 UI 交互；
- 不同循环预算是统一管理还是由子图分别管理；
- 哪些科学诊断值得并行，哪些必须保持顺序。

## 方向二：Codex Handoff 向图内 Code Agent 升级

### 方向目标

把当前“图内节点生成任务、图外 Codex worker 完成编码”的模式，升级为“LangGraph 负责管理完整 Code Agent 生命周期”的模式。

这里的“图内”是控制意义上的图内，而不是要求 Code Agent 与主科研图在同一个 Python 进程中直接修改正在运行的源码。

### 当前模式的价值与限制

当前 Codex Handoff 并不是无用的临时设计。它已经提供了重要基础：

- coder task packet；
- code change summary；
- tests status；
- allowlisted verification；
- 失败后返回 Codex 的基本路线；
- 手动和自动 worker 之间的边界。

A02 将这个 physical node 的 canonical Attempt kind 固定为 `legacy_codex_handoff`。它不是 `code_agent`；A02 fallback harness 中出现的 canonical `code_agent` 也只是 transition protocol sink。Fake/real graph-managed Code Agent 的输入输出、sandbox 和 lifecycle 仍由 A05 与后续 Phase B/C 实现。

它的主要限制是：

- 编码过程本身对 LangGraph 来说仍是黑盒；
- 图只能读取最终文件，难以管理编码中的工具调用、预算和中间失败；
- 外部 worker 直接操作当前仓库时，隔离和并行能力有限；
- Code Agent 的失败类型和下一步建议还没有成为稳定的结构化协议；
- 真实 Code Agent 与图的 path harness 尚未完全解耦。

### 目标形态

未来 Code Agent 更适合成为一个受控子图或受控 Agent runtime，概念上包括：

```text
Validate task
→ Inspect repository and failure evidence
→ Propose bounded change plan
→ Apply changes in isolated workspace
→ Run required checks
→ Inspect diff and scope
→ Return structured result
```

主图只需要消费稳定的 Code Agent result contract，不需要理解每一次 shell command 或文件修改细节。

### 先定义 Code Agent Contract

在修复全部图路线之前，需要先讨论 Code Agent 的最小契约。它至少应表达：

- 触发代码修改的原因和证据；
- 基准 commit 或代码版本；
- 允许修改的范围；
- 禁止修改的范围；
- 要求运行的验证；
- attempt、tool、token 和时间预算；
- 代码修改结果；
- changed files、patch 或 diff identity；
- tests 和 scope checks 结果；
- 失败类型；
- 是否值得重试；
- 是否需要人类批准；
- 是否可以进入新的 Analysis attempt。

Contract 确认后，图的 harness 可以先使用 Fake Code Agent 返回成功、失败、无需修改、预算耗尽和需要人工介入等结果。

### 隔离执行原则

真实 Code Agent 不应直接在主图正在使用的工作目录中无边界修改代码。优先方向是：

- 每个 code attempt 使用独立 worktree、container 或 sandbox；
- 记录 base commit、workspace identity 和 patch hash；
- 只把经过验证的 patch/result 交回控制层；
- 主图决定是否接受修改并创建新的 Analysis attempt；
- 修改后的分析最好由 fresh subprocess 或独立执行环境运行；
- 多个 code attempts 不共享可变工作目录；
- raw data、accepted results、secrets 和不允许的目录继续受到硬边界保护。

这样可以避免运行中的 Python 模块缓存、checkpoint 对应的代码版本和磁盘源码互相不一致。

### Code Agent 的自主边界

Code Agent 可以：

- 阅读相关源码、测试和失败 artifacts；
- 制定局部修改方案；
- 在授权范围内修改；
- 运行明确验证；
- 根据测试结果进行有限重试；
- 返回无法安全完成的原因。

Code Agent 不应：

- 修改 raw data 或 accepted scientific results；
- 自己改变 Human Gate 和 risk floor；
- 自己扩大 Allowed Files；
- 因测试失败而无限重试；
- 在没有新证据时重复同一种修复；
- 自己决定 paper-level physics conclusion；
- 在未授权情况下将修改 push 或 merge 到正式分支。

### 与图可靠性方向的关系

这个方向与方向一不是简单的前后串行关系：

1. 先在方向二中定义最小 Code Agent contract；
2. 方向一使用 Fake Code Agent 打通和测试控制路线；
3. 再实现真实的图内 Code Agent；
4. 用同一套 trajectory 和 cycle harness 替换 Fake 实现进行集成验证。

因此不会在修图时凭空假设 Codex 路由，也不会让真实 Codex 的不确定性阻塞控制层测试。

### 本方向达到阶段性成熟的标志

- Code Agent 输入输出是稳定、可校验的结构化合同；
- Fake 和真实 Code Agent 可以在不修改主图 routing 的情况下替换；
- 每个 code attempt 有独立 workspace 和 identity；
- patch、测试、失败和预算都有完整 provenance；
- 代码修改成功后进入新的 Analysis attempt，而不是覆盖旧结果；
- 测试失败、scope violation 和重复失败都有明确停止路线；
- Code Agent 无法绕过安全边界和 Human Gate；
- 同一个失败场景可以分别判断是 graph harness 问题还是 Code Agent 能力问题。

### 后续需要讨论的问题

- Code Agent 使用独立 LangGraph subgraph、Codex SDK，还是受控 CLI adapter；
- worktree、container 和 remote sandbox 的选择；
- patch 接受和合并由哪个节点负责；
- 代码修改后如何创建 fresh analysis environment；
- Code Agent 的最小和最大工具集合；
- failure fingerprint 和重复失败判断方式；
- 哪些修改必须 Human Approval；
- 如何评估 Code Agent 的能力，而不只评估测试是否通过。

## 方向三：Agent 物理知识与专业能力升级

### 方向目标

在控制层可靠之后，逐步提升每个 Agent 对 LQCD、quasi-DA、数据质量、拟合、系统误差和科研证据的理解，使 Agent 不仅能够生成结构正确的结果，还能够做出更有依据、更精确的专业建议。

这个方向不等于“给每个 Agent 都加一个 RAG”。需要先确定不同 Agent 缺少什么能力，再决定应通过 deterministic tool、curated knowledge、RAG、Prompt、程序注册表还是新的专门节点补足。

### 为什么不优先把全部 PDF 交给 Coordinator

Decision Coordinator 的核心职责是汇总已经形成的结构化证据、执行风险规则并决定下一步。它不应该成为第二个独立 Scientific Reviewer，也不应仅凭检索到的论文片段推翻确定性诊断或 Reviewer 的证据。

如果 Coordinator 同时负责广泛检索、物理分析和最终路由，会产生：

- 职责重叠；
- 证据来源不清；
- Reviewer 与 Coordinator 给出相互竞争的物理结论；
- 路由决策被检索噪声直接影响；
- 很难判断错误来自检索、推理还是风险规则。

更合理的方向是建立共享、可审计的 Physics Knowledge Service，并给不同 Agent 提供不同类型的 evidence bundle。

### 共享 Physics Knowledge Service

未来的物理知识能力应倾向于共享底层服务，而不是每个 Agent 建立互不兼容的向量库。服务输出应尽量结构化，例如：

- claim 或 knowledge item；
- source identity；
- document version 或 checksum；
- page、section 或 equation location；
- bounded excerpt；
- retrieval score；
- applicable observables/methods；
- uncertainty 或 conflict indicator；
- retrieval timestamp/config version。

Agent 使用的是 evidence bundle，而不是直接把整本 PDF 放进 prompt。最终设计还需要解决公式、表格、扫描 PDF、引用定位和版本管理问题。

### 知识来源需要分层

至少应区分：

1. **Run-specific evidence**：当前 case 的 config、fit result、diagnostics、manifest 和 human decision；
2. **Project knowledge**：本项目已经批准的方法、规范、历史 decisions 和 accepted practices；
3. **Literature knowledge**：论文、综述、方法文档和外部参考资料；
4. **Policy knowledge**：安全边界、风险规则、approval 条件和 artifact contract。

这些知识的权威性不同，不能在同一个无差别相似度检索结果中直接混合。当前运行的真实数值证据必须优先于一般文献描述；项目安全策略也不能被外部论文覆盖。

### 不同 Agent 的能力升级方向

#### Method Planner

重点能力：

- 根据 observable、ensemble 和目标选择合适的方法步骤；
- 识别必要输入和缺失输入；
- 查找相关方法依据和先决条件；
- 区分已实现程序与需要开发的新能力；
- 生成带证据和不确定性的 method plan。

它适合使用方法学检索、项目 capability registry 和历史 plan evidence，但不负责最终接受某个物理结果。

#### Code Agent

重点能力：

- 理解项目架构和 artifact contracts；
- 根据失败证据进行局部修复；
- 选择正确测试和分析入口；
- 避免违反科研数据边界；
- 识别修复是否改变科学方法而需要 Human Gate。

它主要需要代码、测试、repo rules 和 task-specific evidence，不应被大量物理论文上下文淹没。涉及科学算法时，可以请求 Method Planner 或 Reviewer 提供结构化方法依据。

#### Analysis Engineer

重点能力：

- 选择和调用已经注册的分析程序；
- 检查输入、输出、单位、维度和 provenance；
- 分类代码、配置、数据和 workflow 失败；
- 生成可复现 execution evidence。

它的核心增强应优先来自可靠工具、program registry、schema 和诊断程序，而不是让 LLM 自由生成分析代码或自由解释数据。

#### Scientific Reviewer

重点能力：

- 结合 correlator、fit 和 matrix-element evidence 识别异常；
- 使用文献或项目标准解释为什么某项检查重要；
- 区分观察、推断、警告和建议；
- 指出证据不足和相互冲突的地方；
- 给出可验证的下一步检查建议。

它是最适合优先试验物理 RAG 的 Agent，但 RAG 只能补充解释和方法依据，不能覆盖 deterministic severe flags。

#### Decision Coordinator

重点能力：

- 汇总不同 Agent 的结构化结果；
- 识别冲突、缺失证据和未解决风险；
- 应用 deterministic safety floor；
- 选择有限的下一步动作；
- 把复杂情况升级给 Human Gate。

它可以读取 Reviewer 提供的 citations 和 evidence bundle，但不应成为主要 literature researcher。

#### Human Approval Gate 与 Memory/Report

Human Gate 需要更清楚地展示：

- 当前 attempt 与历史 attempt 的差异；
- 风险来自什么证据；
- Agent 建议了什么；
- 哪些问题仍未知；
- 批准不同动作的影响。

Memory/Report 需要保存已经批准的证据和决策，而不是把所有 Agent 生成内容自动转化为长期知识。

### RAG 本身也需要 Harness

RAG 是否有效不能只看回答“更像专家”。至少需要评估：

- 是否检索到正确来源；
- citation 是否真的支持 claim；
- page/section 定位是否正确；
- 是否遗漏关键反例或冲突来源；
- 没有足够证据时是否会 abstain；
- RAG 是否改善规划、review 或风险识别；
- 是否增加无关上下文和错误自信；
- 不同文档版本是否可复现；
- no-RAG 与 RAG 是否在固定 case set 上有可测差异。

物理 RAG 的成功标准不能仅由另一个 LLM 判断，应尽量加入专家标注、source checks、citation checks 和确定性行为预期。

### 本方向达到阶段性成熟的标志

- 每个 Agent 的能力缺口和增强手段被分别定义；
- 共享知识服务能够返回可追踪 evidence bundle；
- literature、project policy 和 run evidence 不会无差别混合；
- Reviewer 的物理建议带有可验证来源；
- Coordinator 不会绕过 Reviewer 和 deterministic safety floor；
- RAG 无证据时能够明确拒答或请求更多信息；
- 固定 benchmark 能显示能力增强带来的收益和代价；
- 新知识版本、Prompt 和模型变化可以进行回归比较。

### 后续需要讨论的问题

- 第一批纳入的 PDF、项目文档和物理主题；
- 谁负责文献筛选、版本确认和专家标注；
- 公式、表格和扫描 PDF 的抽取质量标准；
- evidence bundle 的正式 schema；
- 第一个 RAG 试点选择 Method Planner 还是 Scientific Reviewer；
- Coordinator 可以访问哪些知识层；
- 如何建立物理问题、来源和 expected behavior 数据集；
- 是否需要新的 Knowledge Curator 或 Retrieval Node，还是保持共享服务即可。

## 三个方向之间的依赖关系

三个方向不是完全独立，也不是简单依次完成后才开始下一个。建议的逻辑关系是：

```text
确认控制层原则和 Code Agent 最小契约
                ↓
复用 A02 identity，建立 invalidation、resume 和 path harness
                ↓
用 Fake Code Agent 验证完整图循环
                ↓
接入隔离的真实 Code Agent
                ↓
在可靠控制层上逐步增强物理知识和 RAG
                ↓
用统一 benchmark 比较整个系统的可靠性与能力
```

其中：

- 方向一是基础主线；
- 方向二需要提前定义接口，但真实实现依赖方向一的控制合同；
- 方向三可以提前准备知识和评估问题，但不应先把 RAG 接入生产路线；
- Harness 贯穿全部方向，不是最后才补的测试工作。

## 建议的阶段划分

以下只是讨论阶段的逻辑划分，不是当前执行 ticket。

### 阶段 A：控制合同澄清

目标是确认：

- 哪些路线必须存在；
- Run/Cycle/Attempt 如何理解（A02 已确认并完成实现验收）；
- 回退后的 artifact invalidation；
- Code Agent 的最小输入输出；
- 循环预算和 Human Gate 边界；
- 哪些行为必须由确定性规则控制。

这一阶段的主要产物是讨论结论和架构决策，不做大规模能力开发。A02 是纠正已发生 design/runtime 偏差的 implementation ticket：它落地 identity protocol，但不提前实现 A03–A07。

### 阶段 B：图和 Harness 可靠性

目标是让 Fake Agents 下的所有允许路线、循环、停止和恢复行为可验证，并建立 trajectory、failure injection 和 checkpoint tests。

这一阶段回答的是“控制系统是否正确”，不评价真实 Code Agent 或 RAG 是否足够聪明。

### 阶段 C：图内 Code Agent

目标是在不改变主图合同的前提下，把 Fake Code Agent 替换为隔离、可审计、可预算的真实实现，并验证代码修复到新 Analysis attempt 的完整闭环。

### 阶段 D：Agent 能力与物理知识

目标是根据固定能力缺口，选择一个或少数 Agent 进行可测的能力增强，优先验证共享 knowledge/evidence contract，再逐步扩大覆盖范围。

### 阶段 E：综合 Benchmark 与稳定版本

目标是把图可靠性、Code Agent、科学判断、RAG、成本和稳定性放入统一评估体系，形成下一次可以单独保存和演示的里程碑。

## 整体成功标准

下一阶段最终不应只用“更多 Agent 已接入”来判断成功。更有意义的成功标准是：

- 一次复杂运行可以解释每个路线选择和每次循环原因；
- 所有旧 attempt 都保留且不会污染当前结论；
- 人类可以在关键节点暂停、检查并安全恢复；
- Code Agent 可以修复有限范围问题并由 tests 和 scope checks 证明；
- 失败时可以区分 graph、Code Agent、analysis、RAG 和 provider 问题；
- Agent 的物理判断有来源、有证据、有 abstention；
- 加入 RAG 或更换模型后能够量化比较收益、成本和回归；
- 高风险科学结果仍然无法绕过确定性规则和 Human Approval；
- 新版本能够形成独立、可复现、可审计的下一阶段 milestone。

## 如果顺序安排错误，可能出现的问题

### 先全面增加 RAG

可能得到看起来更专业的回答，但图的循环、状态和失效规则仍然不可靠，而且更难定位错误来源。

### 先实现高度自治的 Code Agent

可能让真实 Code Agent 在当前仓库不断修改和重试，但外围没有稳定 attempt、预算、sandbox 和恢复协议。

### 先画出所有回退边

如果没有 invalidation、artifact namespace 和停止条件，更多边只会增加旧数据污染和无限循环风险。

### 只做真实 LLM 端到端测试

失败时无法判断是路由、状态、工具、Prompt、模型还是科学判断问题；测试结果也容易受到随机性影响。

### 只做节点单元测试

每个节点可能单独正确，但组合后的循环、checkpoint、并行和 Human Gate 仍可能失败。

## 下一轮讨论建议

当前 A01 transition matrix 与 A02 identity model 已确认。后续 ticket 应从尚未解决的问题继续，而不是重新讨论这两项：

1. 四种主要回退的 artifact invalidation 规则；
2. Human Gate 的 PAUSE/resume 语义；
3. Code Agent 的最小输入输出 contract；
4. budgets、failure fingerprint 和停止条件；
5. Fake Code Agent 需要模拟的结果类型；
6. 哪些 harness 属于 Phase B 的必要基线；
7. 第一个物理能力增强试点及其可测问题；
8. 共享 Physics Knowledge Service 的 evidence bundle；
9. 下一阶段 milestone 的演示场景和验收定义。

这些问题确认之后，再决定是否更新 `ARCHITECTURE.md`、`STATE_SCHEMA.md`、`ARTIFACT_CONTRACTS.md`、`EVALS_AND_OBSERVABILITY.md` 和 `AGENT_ROLES_AND_BOUNDARIES.md`，并进一步拆分正式执行 tickets。

## 与现有文档的关系

- [`docs/README.md`](README.md)：第二阶段文档入口与权威顺序；
- [`tickets/README.md`](tickets/README.md)：ticket 生命周期和 Phase A–E 目录；
- [`REPO_CURRENT_STATE.md`](REPO_CURRENT_STATE.md)：只记录当前已经实现、验证和正在进行的工作；
- `ARCHITECTURE.md`：记录 current-route identity protocol，并把 A02 harness-only fallback 与未来产品路线分开；
- `STATE_SCHEMA.md`：已经接收 A02 Run/Cycle/Attempt/Transition/Human identity，未来只接收经过批准的 reducer 或恢复字段；
- `ARTIFACT_CONTRACTS.md`：已经接收 A02 execution ledger 与 approval 0.2，未来只接收经过批准的 domain-artifact namespace 和 evidence bundle；
- `EVALS_AND_OBSERVABILITY.md`：未来接收已经批准的 harness 和 benchmark 设计；
- `AGENT_ROLES_AND_BOUNDARIES.md`：未来接收 Code Agent 和物理知识能力的正式边界；
- 第一阶段单体 build plan、ticket ledger 和 prompt playbook 已在迁移审计后从当前工作树删除；原文可从 Git tag `v0.2-demo` 查看。

本文在现阶段只负责连接“当前成熟 Demo”与“下一阶段系统提升”之间的设计讨论。Phase A 的讨论入口是 [`tickets/phase-a-control-contracts/OVERVIEW.md`](tickets/phase-a-control-contracts/OVERVIEW.md)。
