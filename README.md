# ireader-dicts

给掌阅 iReader 墨水屏阅读器（在 Ocean 4 Turbo 上测试过）做英汉词典的小工具：

1. **扩充自带词库**：逆向了阅读器自带的有道离线词典格式（`.ydd` + `yddict.idx`），在保留原有词条、音标和词形的前提下，把 [ECDICT](https://github.com/skywind3000/ECDICT) 的英文释义和考试标签（四六级、考研、托福、雅思、GRE）追加进去。
2. **生成外挂词典**：用 ECDICT 生成带音标的 Kindle 格式 `.mobi` 词典，放进阅读器的 `iReader/dict` 目录就能用。

| 文件 | 作用 |
|---|---|
| `ydd_format.py` | 有道 `.ydd` / `.idx` 格式的读写库，文件头注释里有完整的格式说明 |
| `build_system_dict.py` | 读取原版词库，合并 ECDICT 后写出新词库 |
| `build_ecdict.py` | 从 ECDICT 生成 Kindle 词典源文件（按 BNC/COCA 词频筛选，控制体积） |
| `restore_system_dict.ps1` | 通过 USB（MTP）把原版或新版词库推回阅读器，替换前会自动备份 |

## 用法

```bash
# 扩充自带词库：先把阅读器根目录的 /dict 拷到 system-dict-backup/dict
python build_system_dict.py system-dict-backup/dict ecdict.csv system-dict-new

# 推到阅读器（USB 连接，选文件传输模式）
powershell -ExecutionPolicy Bypass -File restore_system_dict.ps1 -Source system-dict-new

# 生成外挂 .mobi 词典（需要 kindlegen）
python build_ecdict.py ecdict.csv build
kindlegen build/ecdict.opf -c1 -dont_append_source
```

`ecdict.csv` 从 [ECDICT](https://github.com/skywind3000/ECDICT) 下载（MIT 许可）。仓库里不包含任何词典数据。

> 改系统词库有风险，请先备份。`restore_system_dict.ps1` 不带参数运行就是还原原版。
