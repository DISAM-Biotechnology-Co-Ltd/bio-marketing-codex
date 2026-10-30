# Codex 版安裝與設定

這份是給人看的說明，SKILL.md 不會引用它。

## 安裝

需要先安裝 git。這是公開 repo，不需要登入 GitHub。

用 git 直接下載到 Codex 的 skills 目錄，資料夾名稱維持 `bio-marketing`：

```bash
git clone https://github.com/DISAM-Biotechnology-Co-Ltd/bio-marketing-codex.git ~/.codex/skills/bio-marketing
```

之後要更新到最新版：

```bash
git -C ~/.codex/skills/bio-marketing pull
```

若 `~/.codex/skills/bio-marketing` 已經存在（例如之前手動複製過），先把它改名或移走再 clone。

重新開啟 Codex 對話後，輸入 `$bio-marketing` 加上產品說明即可啟動。`agents/openai.yaml` 設定了 `allow_implicit_invocation: false`，所以只有明確輸入 `$bio-marketing` 才會啟動，不會在一般生技問題中被自動帶入。

註：OpenAI 現行文件也列出 `$HOME/.agents/skills` 與 repo 內的 `.agents/skills` 作為 skill 位置。若之後要讓整個團隊共用，可以把這個資料夾放進共用 repo 的 `.agents/skills/bio-marketing/`。

## 必要條件

- **網路搜尋**：文獻與法規查證需要網路搜尋。沒有網路搜尋時，skill 會把未查證的文獻全部標 E7，並告訴 PM。設定鍵名以官方 config reference 為準：https://learn.chatgpt.com/docs/config-file/config-reference
- **Python 3**：`scripts/check_claims.py` 只用標準函式庫，不需安裝套件。

## 選單式提問（建議開啟）

Codex 有原生的提問工具 `request_user_input`，會跳出選單讓 PM 點選，比打數字回覆穩定。它預設只在 **Plan mode** 開放；一般模式要在 `~/.codex/config.toml` 開啟實驗功能：

```toml
suppress_unstable_features_warning = true   # 選填：關掉實驗功能警告，必須放在檔案最上方、任何 [區塊] 之前

[features]
default_mode_request_user_input = true
```

- 已經有 `[features]` 區塊的話，把那一行加進原本的區塊，不要重複寫 `[features]`。
- 這是未寫進官方文件的實驗功能，Codex 更新後可能改名或移除。可用 `codex features list` 確認目前名稱與狀態。
- 沒開也能用：skill 會改用編號文字選項提問，PM 回覆數字即可。
- `codex exec` 與 subagent 不支援這個工具，一律走編號文字選項。

## 鎖定模型（減少模型更新造成的行為漂移）

skill 本身無法指定模型，要在 Codex 設定中鎖定。建議為這個 skill 建一個 profile，例如 `~/.codex/bio-marketing.config.toml`：

```toml
model = "<填入目前帳號可用、且已跑過 evals 的模型>"
model_reasoning_effort = "high"
```

使用時以 `--profile bio-marketing` 啟動（CLI），或在 Codex app 的設定中選同一個模型與推理強度。

模型名稱不要寫死在這份說明裡：模型會退役，換模型前請先跑過 `evals/cases.md`。

## 每次模型更新後

1. 在新的 Codex 對話依 `evals/cases.md` 逐案執行。
2. 把結果記到「紀錄表（Codex 版）」，模型與 reasoning effort 都要寫。
3. 任何一項「不可」發生，就先不要換模型，回頭修 SKILL.md 或 references。

`check_claims.py` 的確定性測試：

```bash
cd ~/.codex/skills/bio-marketing/scripts && python3 test_check_claims.py
```
