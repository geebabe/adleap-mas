# Policy2Action: Preliminary Benchmark Results

| Policy Name               | Type               | Task Completed   | Policy Compliance   |   Total Steps | Detour Overhead   |   Elapsed Time (s) |
|:--------------------------|:-------------------|:-----------------|:--------------------|--------------:|:------------------|-------------------:|
| Unconstrained Optimal     | Optimization       | 3/3 (100%)       | 100%                |            23 | 0.0% (Baseline)   |              12.06 |
| Lightest First            | Attribute Priority | 3/3 (100%)       | 100%                |            26 | +13.0%            |               7.87 |
| Heaviest First            | Attribute Priority | 3/3 (100%)       | 100%                |            31 | +34.8%            |               8.5  |
| Spatial (North First)     | Spatial Constraint | 3/3 (100%)       | 100%                |            23 | +0.0%             |               9.21 |
| Multilingual (Vietnamese) | Cross-Lingual      | 3/3 (100%)       | 100%                |            23 | +0.0%             |               8.82 |
