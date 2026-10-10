# 从证据到行动

比较以用户决策为中心。先明确维度的 definition、comparison_basis 和 unit，再填矩阵。不要用功能总数代替适合度，也不要从“竞品有”直接推出“我们应该做”。同样严谨地审视自家产品和竞品。

## 执行模式

- 快速比较：适用于用户已经指定产品及价格、套餐、功能或其他少量明确维度的请求。只核验影响这些维度的关键事实，默认交付核心结论、紧凑比较矩阵、重要不确定性和关键来源；不自动扩展定位、用户体验、策略或建议。可以保持 findings、recommendations 为空。
- 深度分析：适用于定位、用户需求与场景、业务流程、体验、竞争策略或产品机会研究。按下述证据到行动链选择相关框架，输出有决策价值的发现和必要建议。

两种模式都必须读取关键原始来源并逐条核验 claim。快速模式减少范围和展示复杂度，不降低证据标准，也不把未知补成结论。

## 发现

finding 必含 finding_id、statement、evidence_claim_ids、comparison_ids、certainty。certainty 为 established / qualified / unresolved。

发现引用支持它的实际主张和比较；原文没有的推断应明确表达为分析。涉及未知或未解决冲突时不可标 established。市场定位宣传不证明实际产品效果；一个用户评论不证明普遍需求。

## 建议

recommendation 必含 recommendation_id、evidence_mapping、user_impact、action、preconditions、conditional、validation。

- evidence_mapping 为非空数组，每项含 finding_id、claim_ids（非空）、supports。claim_ids 必须来自该 finding 的 evidence_claim_ids；supports 说明证据支持什么及其边界。
- user_impact 含 statement、basis（evidence / hypothesis）、claim_ids。basis=evidence 时必须有实际证据；没有用户影响证据时用 hypothesis。
- action 描述具体动作，不捏造优先级、成本、留存或收入收益。
- preconditions 每项含 statement、state（confirmed / unconfirmed / rejected）、assumption_id（可空，若有必须指向 scope.assumptions 并保持状态一致）。
- conditional 为布尔值。缺少 scope.own_product_id 时所有建议必须为 true，并说明未确认的自家产品或用户场景前提。有任何未确认或已拒绝前提时也不能写成无条件建议。
- validation 含 method、metric、success_criterion、criterion_status。criterion_status 为 to_be_defined / proposed / confirmed，分别表示待定义、建议阈值和已确认阈值；不得把自定阈值标为用户确认。

每条建议至少关联一个发现和一个有效主张。纯比较请求不强制生成建议。未解决的事实冲突只能支撑补充验证或条件性探索，不能直接支撑确定性的开发结论。

## 推导顺序

证据 → 发现 → 对目标用户的影响（证据或假设）→ 建议动作 → 前置条件 → 验证方式。

例如，文档披露并发编辑人数上限，只能支持存在套餐限制这一事实。若用户群确有高并发协作任务，可建议先观察阻碍发生频率，再决定是否调整限制；不能直接宣称放开限制将提高留存。

## 交付复核

核对每条结论、发现和建议能追溯到原文；标记未知、冲突和前提；不要隐藏竞品优势。若达到研究预算仍有决策相关缺口，phase=completed_with_gaps，limitations 写明缺口及可能影响。报告可以简短，但不得省略影响结论的适用条件和时间基准。
