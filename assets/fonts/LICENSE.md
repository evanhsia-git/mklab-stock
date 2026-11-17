Inter 與 Noto Sans TC 字型授權說明
=====================================

本目錄下的 WOFF2 字型檔皆為自由開源授權（SIL Open Font License 1.1），
允許自由使用、修改與再散布（包含自託管於網站），僅要求保留授權聲明。

字型來源與授權
--------------

1. Inter
   - 作者：Rasmus Andersson
   - 官方網站：https://rsms.me/inter/
   - 官方原始碼：https://github.com/rsms/inter
   - 授權：SIL Open Font License 1.1
   - 授權全文：https://github.com/rsms/inter/blob/master/LICENSE.txt

2. Noto Sans TC（思源黑體 繁體中文）
   - 作者：Google / Adobe（Noto 專案）
   - 官方網站：https://fonts.google.com/noto/specimen/Noto+Sans+TC
   - 官方原始碼：https://github.com/notofonts/noto-cjk
   - 授權：SIL Open Font License 1.1
   - 授權全文：https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE

檔案說明
--------

本網站使用的字型檔（inter-w400/500/600/700.woff2、noto-400/500/600/700.woff2）
皆是從上述官方來源取得完整字型後，以 fonttools（Python 套件，非網站執行依賴）
針對本網站實際使用到的字元集做 Unicode 子集化（subset）並轉為 WOFF2 格式，
以縮小檔案體積、加快載入。子集化僅裁切未使用的字符，不修改字型設計，
仍受原 OFL 1.1 授權規範。

SIL Open Font License 1.1 摘要
-------------------------------
- 允許自由使用、研究、修改與再散布（含商業用途）
- 允許嵌入文件與網站自託管
- 不得單獨販售字型檔本身
- 修改後的衍生字型不得使用原保留字型名稱（Reserved Font Name）
- 散布時須保留本授權聲明

完整授權條文請見上述各字型官方連結。
