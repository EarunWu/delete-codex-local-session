简体中文 | [English](./README.en.md)

# delete-codex-local-session

一个用于按会话 ID 检查并删除本地 Codex 会话的 skill。

这个 skill 只用于清理本地 Codex 存储，不会删除云端或账号层面的聊天记录。

## 功能

- 先预览某个会话 ID 在本地命中了哪些文件和数据库记录
- 删除 `sessions/` 和 `archived_sessions/` 下对应的 transcript 文件
- 删除 `session_index.jsonl` 中对应的索引项
- 删除 `state*.sqlite` 中对应的记录
- 删除 `logs*.sqlite` 中对应的日志记录
- 删除 `generated_images/<session-id>/` 下对应的图片目录
- 删除 `.codex-global-state.json` 中与该会话 ID 精确匹配的键或值

## 安全机制

- 默认只做预览
- 只有加上 `--apply` 才会真正删除
- `--vacuum` 是可选项，用于在删除后压缩被修改的 SQLite 数据库
- `--keep-global-state` 可用于保留 `.codex-global-state.json` 不变

## 安装方法

把这个仓库的内容放到你的 Codex skills 目录中，目录应为：

```text
~/.codex/skills/delete-codex-local-session/
```

在 Windows 上通常对应：

```text
C:\Users\<你的用户名>\.codex\skills\delete-codex-local-session\
```

最终目录结构应当类似：

```text
delete-codex-local-session/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── scripts/
    └── delete_codex_local_session.py
```

## 在 Codex 对话中使用

你可以显式点名这个 skill：

```text
用 $delete-codex-local-session 预览本地会话 019d...
用 $delete-codex-local-session 删除本地会话 019d...
```

## 在命令行中使用

只预览，不删除：

```powershell
python scripts/delete_codex_local_session.py <session-id>
```

真正删除本地会话：

```powershell
python scripts/delete_codex_local_session.py <session-id> --apply
```

删除并顺便压缩 SQLite 数据库：

```powershell
python scripts/delete_codex_local_session.py <session-id> --apply --vacuum
```

删除时保留 `.codex-global-state.json` 不变：

```powershell
python scripts/delete_codex_local_session.py <session-id> --apply --keep-global-state
```

## 使用建议

- 条件允许时，先关闭 Codex app 再删除会话
- 如果删除后界面里仍然显示旧线程，可以重启 Codex app
- 每次删除前都建议先运行一次预览模式

## 运行要求

- Python 3
- 自带脚本不依赖第三方 Python 包

## 仓库内容

- `SKILL.md`：skill 的触发说明与使用流程
- `agents/openai.yaml`：UI 展示相关元数据
- `scripts/delete_codex_local_session.py`：实际执行清理的脚本

## 限制

- 仅清理本地数据，不会删除服务端或账号层面的聊天记录
- 即使本地已删除，Codex 界面也可能因为缓存暂时显示旧线程
