# 输入与案例存储接入说明

普通入口以 `liuyao_input_schema.json` 为准，只含 `question`、自初至上的六项 `lines`，以及可选 `actual_cast_time`。后台案例导出结构见 `case_record_schema.json`。前端不能把案例记录结构当作可写请求提交。

`validate_input.py` 是针对当前三字段契约的标准库校验器，提供 `validate_input(data)`、`derive_six_lines(data)`。它没有运行通用JSON Schema标准引擎；文档中的Schema供正式应用选择符合标准的验证工具接入。四象转换只处理阴阳与动静，完整基础排盘使用 `base_chart.py`。

`CaseStore` 使用标准库SQLite。每个写操作在事务中保存业务记录与幂等结果；同owner、同操作、同幂等键只能对应同一请求内容。数据库不可变触发器防止直接覆盖历史数据。SQL文件负责表结构，Python初始化同时安装追加保护触发器。

## 可信调用上下文

`Actor(owner_id, session_id)` 必须由未来HTTP服务的认证会话构造，不从客户端请求正文取值。现有程序核对actor与case归属，也拒绝将另一个case的run或反馈错接到当前case；它没有实现密码、cookie、令牌或浏览器会话认证。调用者能任意构造Actor的本地开发环境不等于真实用户已认证。

用户只输入问题和卦；背景、澄清和反馈在实际服务过程中逐步加入。案例使用默认私密的服务记录策略。`public_use`、`training_use`始终为false，不提供把案例自动用于公开或训练的接口。

## 主要方法

| 方法 | 关键参数和返回 |
|---|---|
| create_case | actor、input_data、idempotency_key；有效返回case_id/revision_seq/recorded_at，无效返回failure_id/errors |
| revise_case | actor、case_id、新input_data、reason、expected_revision_seq、idempotency_key；追加修订 |
| append_context_event | actor、case_id、event_type、content、idempotency_key；追加上下文 |
| start_analysis | actor、case_id、source_hash/rules_digest/prompt_digest/engine_build、幂等键；可传expected_revision_seq和同案例parent_run_id |
| finish_analysis | actor、case_id、analysis_run_id、status、幂等键；保存chart_snapshot/evidence/report/validation/unresolved/error |
| add_ai_event | actor、case_id、run、stage、attempt_id、raw_output、parse_status、validation_errors、幂等键；可附adopted_output和model_run_metadata |
| add_feedback | actor、case_id、reported_outcome、幂等键；可关联run、occurred_at、verification_status/method、被更正feedback_id |
| export_case / list_cases | 按owner读取案例；导出包含原输入、所有修订、上下文、运行、AI尝试与反馈 |
| export_intake_failures | 按owner导出不合格入口及相关字段错误；不存额外输入字段值 |

所有函数均为本地服务方法，不是已经部署的API。`idempotency_key`属于网络重试与服务编排元数据，不是需要用户填写的额外问题字段。

## 自动积累与快照

`create_case`在入口有效时同时创建首次修订，原始问题和六爻不会被AI摘要替换。无效请求写入`intake_failures`，只保留本服务三字段及错误信息，不把未知额外字段值扩散到案例数据。

每次`start_analysis`读取当时最新输入修订和已有上下文事件，复制为不可变`input_snapshot`，其内容摘要作为`input_snapshot_id`。新问题、更正和新上下文不会回写旧快照。再次分析新建run，可以用同案例parent_run_id保持关联。

`analyzed_at`表示分析开始；终态另有recorded_at。`source_hash`、`rules_digest`、`prompt_digest`和`engine_build`由可信程序传入。run的prompt_digest表示整包摘要，每个AI尝试的model_run_metadata还应保存stage_prompt_digest、input_projection_digest及模型实际标识。摘要对应的源文件和配置正文需要由资料/程序资源库保留，本存储不替代内容资源库。

结果通过`analysis_outcomes`追加，终态为completed、partial、unresolved或failed。completed仅表示本次服务处理完成，不表示预测准确；partial/unresolved需要未解决事项，failed需要错误内容。已结束运行不能覆盖报告或继续添入新的AI尝试，应开新run。

存储保留AI原始文本与程序校验结果。只有parse_status为parsed且validation_errors为空时才允许adopted_output。此前仍须调用AI契约验证器；这些字段不能由客户端自行宣称。存储成功不验证自然语言推论、依据方向或现实效果。AI事件可保留invalid_json、provider_error和未采用内容，避免只留下最后一次成功尝试。

## 时间与反馈

actual_cast_time缺失保持null；服务器录入时间不代替起卦时间。每个修订的time_context记录precision及provenance，当前完整时刻来源为user_supplied。日期不完整时作为相关背景事实留存，例如`{fact:"actual_cast_date", value:"2026-09-10", precision:"day", provenance:"user_reported"}`。历法精度适配与“现在起卦”按钮仍待应用接入。

反馈occurred_at为据称发生时间，recorded_at为服务器收录时间，二者分开。verification_status区分self_reported、externally_supported、disputed、unknown；外部支持必须附方法。服务层应控制谁有权标注核实状态，本存储不验证凭证真伪。反馈更正追加并引用同案例supersedes_feedback_id；不删除原说法，也不覆盖原报告。未反馈不自动产生预测成败标签。

## 尚待应用接入

HTTP API、身份认证、用户界面、实际模型供应商、限流与队列、调用取消、运行超时、时间先后异常提示、领域推论评估、权限分级、用户授权删除、保留周期、备份和恢复仍需实现。为满足用户删除要求，正式服务要设计受控擦除路径及备份/索引处理；不能把本开发基础中的防误删触发器当作永久保留授权。

`test_case_store.py`目前检查21项输入和SQLite业务行为，结果写入`case_store_test_results.json`。测试使用临时数据库和工程数据，未调用AI，也未把合成记录计为真实卦例。
