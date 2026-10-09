# Team 套餐价格与离线编辑比较

> 合成离线测试，非真实产品事实。AtlasBoard 和 MosaicDesk 为测试产品；价格不得用于采购决策。

研究基准：2026-10-09T09:00:00+08:00 · 资料模式：fixture · 状态：completed_with_gaps

## 执行摘要

AtlasBoard Team 的测试价格自 2026-10-01 从 USD 8 调整为 USD 12/席位/月，MosaicDesk Team 为 USD 10/席位/月，均按月承诺。离线编辑方面，AtlasBoard 资料未提及，状态为未知；MosaicDesk 明确不支持。公开材料不足以据此判断整体产品优劣。

## 产品定位与研究范围

| 产品 | 定位 | 范围 |
| --- | --- | --- |
| AtlasBoard | 资料不足，不推断目标市场 | Team，公开价格与功能资料 |
| MosaicDesk | 资料不足，不推断目标市场 | Team，公开价格与离线帮助 |

比较口径：USD，每席位每月，按月承诺。不含企业定制合同。地域未披露，仅比较资料所列公开条件，实际地域适用性仍需确认。未提供自家产品背景。

## 核心对比矩阵

| 维度 | AtlasBoard Team | MosaicDesk Team | 主张与证据 |
| --- | --- | --- | --- |
| 每席位月费（按月承诺） | USD 12 | USD 10 | c-new → atlas-new；c-mosaic-price → mosaic-price |
| 离线编辑 | 未知 | 明确不支持 | c-unknown → atlas-features；c-negative → mosaic-offline |

“未知”不等于“不支持”；不能按该矩阵认定 AtlasBoard 具备离线优势。

## 关键发现与风险

f-offline：MosaicDesk Team 帮助明确写明不支持离线编辑；AtlasBoard 只披露在线编辑、评论和分享，不足以判断离线能力。确定程度为 qualified。

价格冲突 cf-price：保留旧价 c-old（USD 8）和新价 c-new（USD 12），两者 conflict_flag 均为 true。新价格页及公告明确 2026-10-01 生效并替代旧价，resolution 为 resolved_by_effective_date，当前选择 c-new。旧价属于历史事实，不删除或认定为虚假。

## 条件式行动建议

r-offline：若自家产品面向需要断网编辑的团队，先访谈并观察任务受阻频率，再决定是否开发离线能力。

- 证据映射：f-offline → c-negative，只证明竞品限制，不证明用户需求。
- 用户影响：网络不稳定可能影响任务，属于 hypothesis。
- 前提：目标用户有断网编辑需求，尚未确认；conditional=true。
- 验证：访谈与任务观察，测量断网导致的任务中断比例；成功阈值待研究前确定。

此项为条件式建议展示，不声称已知自家短板或已验证收益。

## 研究局限

AtlasBoard 离线状态未知。没有真实产品实测、用户研究或自家背景。全部为合成资料，数据仅用于演示证据追溯与冲突处理。

## 信源列表

所有来源均为本地合成 HTML，访问状态 accessed，模拟访问时间为 2026-10-09T09:00:00+08:00。身份 URL 保存在契约中，.invalid 地址不能联网访问。

| source_id / 本地资料 | 类型 | 发布 / 生效时间 |
| --- | --- | --- |
| [atlas-old](../../tests/fixtures/case-03/atlas-old.html) | pricing_page | 2026-01-01 / 2026-01-01 |
| [atlas-new](../../tests/fixtures/case-03/atlas-new.html) | pricing_page | 2026-09-20 / 2026-10-01 |
| [atlas-announcement](../../tests/fixtures/case-03/atlas-announcement.html) | changelog | 2026-09-20 / 2026-10-01 |
| [atlas-features](../../tests/fixtures/case-03/atlas-features.html) | official_doc | 未知 / 未知 |
| [mosaic-price](../../tests/fixtures/case-03/mosaic-price.html) | pricing_page | 未知 / 未知 |
| [mosaic-offline](../../tests/fixtures/case-03/mosaic-offline.html) | official_doc | 未知 / 未知 |

独立数据文件：[research_contract.json](research_contract.json)。下方内嵌 JSON 与该文件解析后完全相同。


## 完整研究契约

```json
{
  "schema_version": "1.0.0",
  "research_id": "example-case-03",
  "phase": "completed_with_gaps",
  "metadata": {
    "created_at": "2026-10-09T09:00:00+08:00",
    "as_of": "2026-10-09T09:00:00+08:00",
    "language": "zh-CN",
    "source_mode": "fixture"
  },
  "scope": {
    "user_request": "对比 AtlasBoard 和 MosaicDesk 的 Team 套餐价格，以及离线编辑支持情况",
    "objective": "比较 Team 价格及离线编辑支持",
    "decision_context": null,
    "target_users": null,
    "own_product_id": null,
    "product_ids": [
      "atlas",
      "mosaic"
    ],
    "dimension_ids": [
      "price",
      "offline"
    ],
    "inclusions": [
      "Team 公开套餐"
    ],
    "exclusions": [
      "定制合同"
    ],
    "assumptions": [],
    "budget": {
      "max_source_reads": 20
    }
  },
  "clarification": {
    "required": false,
    "reason_codes": [],
    "questions": []
  },
  "products": [
    {
      "product_id": "atlas",
      "name": "AtlasBoard",
      "official_url": null,
      "role": "competitor",
      "context_origin": "fixture"
    },
    {
      "product_id": "mosaic",
      "name": "MosaicDesk",
      "official_url": null,
      "role": "competitor",
      "context_origin": "fixture"
    }
  ],
  "dimensions": [
    {
      "dimension_id": "price",
      "name": "Team 价格",
      "kind": "price",
      "definition": "按月承诺的每席位月费",
      "comparison_basis": "USD，Team，同一公开地区",
      "unit": "USD/seat/month"
    },
    {
      "dimension_id": "offline",
      "name": "离线编辑",
      "kind": "capability",
      "definition": "断网时编辑文档",
      "comparison_basis": "Team",
      "unit": null
    }
  ],
  "sources": [
    {
      "source_id": "atlas-old",
      "source_url": "https://atlas-old.invalid/page",
      "title": "AtlasBoard old Team price",
      "source_type": "pricing_page",
      "access_status": "accessed",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": "2026-01-01T00:00:00+08:00",
        "effective_from": "2026-01-01T00:00:00+08:00",
        "effective_to": null
      },
      "locator": "body",
      "fixture_path": "tests/fixtures/case-03/atlas-old.html",
      "content_sha256": "63a9196bfbecbbb2b5b69d7c3933a5e9e3cc653bb3254b8b5dfd258f9684bd41"
    },
    {
      "source_id": "atlas-new",
      "source_url": "https://atlas-new.invalid/page",
      "title": "AtlasBoard new Team price",
      "source_type": "pricing_page",
      "access_status": "accessed",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": "2026-09-20T00:00:00+08:00",
        "effective_from": "2026-10-01T00:00:00+08:00",
        "effective_to": null
      },
      "locator": "body",
      "fixture_path": "tests/fixtures/case-03/atlas-new.html",
      "content_sha256": "c9e9afaa55e6c640c0ce1804a3bf03f31cb9d030dfa7682f6a1d40caa5c0ba83"
    },
    {
      "source_id": "atlas-announcement",
      "source_url": "https://atlas-announcement.invalid/page",
      "title": "AtlasBoard price announcement",
      "source_type": "changelog",
      "access_status": "accessed",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": "2026-09-20T00:00:00+08:00",
        "effective_from": "2026-10-01T00:00:00+08:00",
        "effective_to": null
      },
      "locator": "body",
      "fixture_path": "tests/fixtures/case-03/atlas-announcement.html",
      "content_sha256": "905f5606e17d63f1b65dedc9d75de1bb31a71142f5005b6f96e07ca2df509f3f"
    },
    {
      "source_id": "atlas-features",
      "source_url": "https://atlas-features.invalid/page",
      "title": "AtlasBoard features",
      "source_type": "official_doc",
      "access_status": "accessed",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": null,
        "effective_from": null,
        "effective_to": null
      },
      "locator": "body",
      "fixture_path": "tests/fixtures/case-03/atlas-features.html",
      "content_sha256": "773c7980febf6af9b241fc4f686addf63fb9b38015b702d2763514fe5d4f0fb3"
    },
    {
      "source_id": "mosaic-price",
      "source_url": "https://mosaic-price.invalid/page",
      "title": "MosaicDesk Team price",
      "source_type": "pricing_page",
      "access_status": "accessed",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": null,
        "effective_from": null,
        "effective_to": null
      },
      "locator": "body",
      "fixture_path": "tests/fixtures/case-03/mosaic-price.html",
      "content_sha256": "211eaba47853c5a0b8e33e9b4642bd5f4139198a41dbe403a6e29ba199a10062"
    },
    {
      "source_id": "mosaic-offline",
      "source_url": "https://mosaic-offline.invalid/page",
      "title": "MosaicDesk offline help",
      "source_type": "official_doc",
      "access_status": "accessed",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": null,
        "effective_from": null,
        "effective_to": null
      },
      "locator": "body",
      "fixture_path": "tests/fixtures/case-03/mosaic-offline.html",
      "content_sha256": "6a217ecff66e65772ba44f9e4120353323a26100a4e132ed405d3ae2a44b96c2"
    }
  ],
  "claims": [
    {
      "claim_id": "c-old",
      "product": "atlas",
      "dimension": "price",
      "claim": "旧 Team 价格为 USD 8",
      "source_id": "atlas-old",
      "source_url": "https://atlas-old.invalid/page",
      "source_type": "pricing_page",
      "quote": "Team costs USD 8 per seat per month with monthly commitment.",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": "2026-01-01T00:00:00+08:00",
        "effective_from": "2026-01-01T00:00:00+08:00",
        "effective_to": null
      },
      "status": "verified",
      "feature_status": null,
      "value": {
        "type": "money",
        "amount": "8",
        "currency": "USD",
        "per": "seat",
        "billing_period": "month",
        "commitment": "monthly"
      },
      "applicability": {
        "plan": "Team",
        "region": null,
        "version": null,
        "billing_period": "month",
        "conditions": []
      },
      "conflict_flag": true
    },
    {
      "claim_id": "c-new",
      "product": "atlas",
      "dimension": "price",
      "claim": "新 Team 价格为 USD 12",
      "source_id": "atlas-new",
      "source_url": "https://atlas-new.invalid/page",
      "source_type": "pricing_page",
      "quote": "Team costs USD 12 per seat per month with monthly commitment. Effective October 1, 2026, replacing the USD 8 price.",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": "2026-09-20T00:00:00+08:00",
        "effective_from": "2026-10-01T00:00:00+08:00",
        "effective_to": null
      },
      "status": "verified",
      "feature_status": null,
      "value": {
        "type": "money",
        "amount": "12",
        "currency": "USD",
        "per": "seat",
        "billing_period": "month",
        "commitment": "monthly"
      },
      "applicability": {
        "plan": "Team",
        "region": null,
        "version": null,
        "billing_period": "month",
        "conditions": []
      },
      "conflict_flag": true
    },
    {
      "claim_id": "c-mosaic-price",
      "product": "mosaic",
      "dimension": "price",
      "claim": "Team 价格为 USD 10",
      "source_id": "mosaic-price",
      "source_url": "https://mosaic-price.invalid/page",
      "source_type": "pricing_page",
      "quote": "Team costs USD 10 per seat per month with monthly commitment.",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": null,
        "effective_from": null,
        "effective_to": null
      },
      "status": "verified",
      "feature_status": null,
      "value": {
        "type": "money",
        "amount": "10",
        "currency": "USD",
        "per": "seat",
        "billing_period": "month",
        "commitment": "monthly"
      },
      "applicability": {
        "plan": "Team",
        "region": null,
        "version": null,
        "billing_period": "month",
        "conditions": []
      },
      "conflict_flag": false
    },
    {
      "claim_id": "c-unknown",
      "product": "atlas",
      "dimension": "offline",
      "claim": "资料不足以判断离线编辑",
      "source_id": "atlas-features",
      "source_url": "https://atlas-features.invalid/page",
      "source_type": "official_doc",
      "quote": "Team includes online editing, comments and sharing.",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": null,
        "effective_from": null,
        "effective_to": null
      },
      "status": "insufficient_evidence",
      "feature_status": "unknown",
      "value": null,
      "applicability": {
        "plan": "Team",
        "region": null,
        "version": null,
        "billing_period": "month",
        "conditions": []
      },
      "conflict_flag": false
    },
    {
      "claim_id": "c-negative",
      "product": "mosaic",
      "dimension": "offline",
      "claim": "Team 不支持离线编辑",
      "source_id": "mosaic-offline",
      "source_url": "https://mosaic-offline.invalid/page",
      "source_type": "official_doc",
      "quote": "Offline editing is not supported on Team. An internet connection is required.",
      "timestamp": {
        "accessed_at": "2026-10-09T09:00:00+08:00",
        "published_at": null,
        "effective_from": null,
        "effective_to": null
      },
      "status": "verified",
      "feature_status": "unsupported",
      "value": null,
      "applicability": {
        "plan": "Team",
        "region": null,
        "version": null,
        "billing_period": "month",
        "conditions": []
      },
      "conflict_flag": false
    }
  ],
  "conflicts": [
    {
      "conflict_id": "cf-price",
      "claim_ids": [
        "c-old",
        "c-new"
      ],
      "reason": "同套餐新旧价格不同",
      "resolution": "resolved_by_effective_date",
      "selected_claim_ids": [
        "c-new"
      ],
      "rationale": "新价格页和公告明确 2026-10-01 生效并替代旧价格"
    }
  ],
  "comparisons": [
    {
      "comparison_id": "cmp-atlas-price",
      "product": "atlas",
      "dimension": "price",
      "feature_status": null,
      "value": {
        "type": "money",
        "amount": "12",
        "currency": "USD",
        "per": "seat",
        "billing_period": "month",
        "commitment": "monthly"
      },
      "assessment_status": "established",
      "evidence_claim_ids": [
        "c-old",
        "c-new"
      ],
      "conflict_ids": [
        "cf-price"
      ],
      "rationale": "依据所列来源和适用时间；未知不代表不支持。"
    },
    {
      "comparison_id": "cmp-mosaic-price",
      "product": "mosaic",
      "dimension": "price",
      "feature_status": null,
      "value": {
        "type": "money",
        "amount": "10",
        "currency": "USD",
        "per": "seat",
        "billing_period": "month",
        "commitment": "monthly"
      },
      "assessment_status": "established",
      "evidence_claim_ids": [
        "c-mosaic-price"
      ],
      "conflict_ids": [],
      "rationale": "依据所列来源和适用时间；未知不代表不支持。"
    },
    {
      "comparison_id": "cmp-atlas-offline",
      "product": "atlas",
      "dimension": "offline",
      "feature_status": "unknown",
      "value": null,
      "assessment_status": "unknown",
      "evidence_claim_ids": [
        "c-unknown"
      ],
      "conflict_ids": [],
      "rationale": "依据所列来源和适用时间；未知不代表不支持。"
    },
    {
      "comparison_id": "cmp-mosaic-offline",
      "product": "mosaic",
      "dimension": "offline",
      "feature_status": "unsupported",
      "value": null,
      "assessment_status": "established",
      "evidence_claim_ids": [
        "c-negative"
      ],
      "conflict_ids": [],
      "rationale": "依据所列来源和适用时间；未知不代表不支持。"
    }
  ],
  "findings": [
    {
      "finding_id": "f-offline",
      "statement": "MosaicDesk Team 文档明确不支持离线编辑，不能推断 AtlasBoard 是否支持",
      "evidence_claim_ids": [
        "c-negative",
        "c-unknown"
      ],
      "comparison_ids": [
        "cmp-mosaic-offline",
        "cmp-atlas-offline"
      ],
      "certainty": "qualified"
    }
  ],
  "recommendations": [
    {
      "recommendation_id": "r-offline",
      "evidence_mapping": [
        {
          "finding_id": "f-offline",
          "claim_ids": [
            "c-negative"
          ],
          "supports": "证明竞品能力限制，不证明目标用户需要离线功能"
        }
      ],
      "user_impact": {
        "statement": "网络不稳定可能影响协作任务",
        "basis": "hypothesis",
        "claim_ids": []
      },
      "action": "若目标用户需要断网工作，先观察任务受阻频率再决定是否开发",
      "preconditions": [
        {
          "statement": "自家产品面向有断网编辑需求的团队",
          "state": "unconfirmed",
          "assumption_id": null
        }
      ],
      "conditional": true,
      "validation": {
        "method": "访谈与任务观察",
        "metric": "断网导致的任务中断比例",
        "success_criterion": "研究前确定阈值",
        "criterion_status": "to_be_defined"
      }
    }
  ],
  "limitations": [
    "AtlasBoard 离线编辑状态未知；合成离线资料不代表真实市场事实。"
  ]
}
```
