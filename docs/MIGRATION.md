# 数据库迁移说明

## 旧式空人物表：profile_id / slug / display_name / details_json

本次按 Windows 实际日志确认的七列旧结构补充兼容：profile_id、owner_id、slug、display_name、details_json、created_at、updated_at；日志中该表 0 行，user_version 为 0。

启动时在事务内确认该旧表仍为空，先自动备份，再将其改名为 person_profiles_legacy_<随机标识> 留存，创建当前人物表。案例、分析快照、模型事件和反馈原记录不改写。若检测到旧式人物表含有记录，则保持保护性停止，避免猜测转换资料。

这一步重建当前人物表的写入结构，避免旧 slug / display_name / details_json 的必填约束影响新增档案。补丁无需删除整个数据库，重复启动不会重复迁移。

## 启动时报 no such column: is_self

原因是已存在的人物表缺少 is_self 字段，之前仅执行 CREATE TABLE IF NOT EXISTS，不会补齐已有表结构。修复后启动时先检查实际字段，再补齐缺失的本人标记和档案元数据，最后建立索引。即使数据库结构编号已经为 5，也会核对实际字段。

关闭软件，完整解压当前软件包，再运行其中的 start.bat。默认继续读取原数据目录，案例、反馈和人物资料无需删除或重建。

需要迁移的现有数据库会先自动备份到原数据目录下的 backups 文件夹，文件名含 before-profile-migration。备份使用 SQLite 备份接口，包含已提交的 WAL 数据。备份失败即停止迁移；档案与反馈字段修改在同一事务中完成，出错则回滚。重复启动不会反复迁移或生成重复备份。

人物新增按字段名写入，兼容旧表追加字段后的不同列顺序；已有额外字段继续保留。新补的本人标记默认为未选中，可在人物档案里自行设为本人。旧表没有创建或更新时间时保持空值，不虚构历史时间。

## 升级前

关闭旧程序，复制备份整个数据目录及模型配置文件。把软件包完整解压到单独程序目录；Windows 默认仍读取原来的 `%LOCALAPPDATA%\Liuyao\data`。

## 自动迁移

打开 cases.sqlite3 时执行增量迁移，数据库版本号设为 5：

1. 新建 `person_profiles`：person_id、owner_id、version、is_self、created_at、updated_at、profile_json。
2. 新建每个 owner 至多一个本人档案的条件唯一索引。
3. 为 `feedback` 追加可空字段 `rules_version`、`match_degree`、`user_notes`。
4. 原 cases、case_revisions、context_events、analysis_runs、analysis_outcomes、ai_events 的列和旧记录不改写。既有历史不可修改触发器继续保留。

人物档案使用独立版本号做并发修改检查。选用档案时保存到 analysis_runs 的输入快照 `person_profile_snapshot`，不把出生资料加入 AI evidence。

规则文件位于数据目录的 `knowledge_base/`。公开构建不再从程序内置参数初始化；首次由用户导入单独取得的 `.lyrules` 加密包或 XLSX。校验通过后先保存 `versions/<版本>.json`，再用原子替换写入当前 `compiled_rules.json`。分析开始后使用冻结参数，即使期间导入新规则，该次分析也不会混用版本。

## 历史与反馈

每次新预测将规则版本、参数快照、engine_build 和模型信息放入结果 JSON，既有 analysis_runs 的 rules_digest 同时包含核心规则目录和实验参数。反馈中 rules_version 从其关联预测读取，不能由客户端伪造。

旧案例和旧反馈没有版本记录时保持空值。重新分析会创建新 run，不覆盖旧结果。反馈仍为追加记录。

## 回退

不要直接把 旧程序接到已经迁移的数据库上：旧程序的反馈插入使用旧列数，会不兼容。需要回退时，关闭当前程序，恢复升级前备份的数据目录，再启动旧程序。保留当前程序的数据副本以免丢失升级后新增记录。
