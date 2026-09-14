# Ticket Completion Records

本目录保存ticket执行后的事实记录。冻结ticket回答“执行前批准了什么”；completion record回答“实际完成了什么”。

规则：

- 每个已执行ticket使用独立文件，不把结果追加回原ticket正文；
- 记录实际changed files、verification、commit、偏差、Stop Condition处理和follow-ups；
- completion record不能新增或改写public contract；合同变化必须进入source-of-truth和新的corrective ticket；
- completion record可以追加事实勘误，但不能伪装成原ticket内容；
- ticket未在执行前commit时，必须明确说明缺少可恢复的committed frozen snapshot。

当前记录：

- [`A02C01_COMPLETION.md`](A02C01_COMPLETION.md)
- [`A04_COMPLETION.md`](A04_COMPLETION.md)
- [`A03_COMPLETION.md`](A03_COMPLETION.md)
- [`A03C01_COMPLETION.md`](A03C01_COMPLETION.md)
- [`G01_COMPLETION.md`](G01_COMPLETION.md)

新记录从[`TEMPLATE.md`](TEMPLATE.md)创建。
