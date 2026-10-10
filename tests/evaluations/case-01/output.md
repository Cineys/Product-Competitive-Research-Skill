# Case 1 模拟输出

> 单次人工模拟；以下为对原始请求的响应，附录用于审计。

你希望分析哪类协作工具，主要用于选型还是规划产品功能？

## 完整研究契约

```json
{
  "schema_version": "1.1.0",
  "research_id": "simulated-case-01",
  "phase": "clarification_required",
  "metadata": {
    "created_at": "2026-10-09T09:00:00+08:00",
    "as_of": "2026-10-09T09:00:00+08:00",
    "language": "zh-CN",
    "source_mode": "fixture"
  },
  "scope": {
    "user_request": "帮我分析协作工具",
    "objective": null,
    "decision_context": null,
    "target_users": null,
    "own_product_id": null,
    "product_ids": [],
    "dimension_ids": [],
    "inclusions": [],
    "exclusions": [],
    "assumptions": [],
    "budget": {
      "max_source_reads": 20
    }
  },
  "clarification": {
    "required": true,
    "reason_codes": [
      "ambiguous_objective"
    ],
    "questions": [
      {
        "question_id": "q-scope",
        "text": "你希望分析哪类协作工具，主要用于选型还是规划产品功能？",
        "resolves": [
          "scope.objective",
          "scope.product_ids"
        ],
        "blocking": true
      }
    ]
  },
  "products": [],
  "dimensions": [],
  "sources": [],
  "claims": [],
  "conflicts": [],
  "comparisons": [],
  "findings": [],
  "recommendations": [],
  "limitations": []
}
```
