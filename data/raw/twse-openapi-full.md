# TWSE OpenAPI 143 端點完整清單（含全部欄位）

- 來源規格：https://openapi.twse.com.tw/v1/swagger.json
- 端點基底：https://openapi.twse.com.tw/v1/opendata/<端點名稱>（免 key，JSON／CSV 皆可）
- 整理時間：2026-11-03；總欄位數：2015

## 分類統計

- 財務報表：30 個端點（891 欄）
- 證券交易：36 個端點（302 欄）
- 公司治理：56 個端點（607 欄）
- 指數：5 個端點（17 欄）
- 券商資料：9 個端點（140 欄）
- 權證：3 個端點（17 欄）
- 其他：4 個端點（41 欄）

---

## 財務報表（30 個）

### t187ap05_L
- 說明：上市公司每月營業收入彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap05_L
- 實測：實測被 WAF 擋
- 欄位（14）：出表日期、資料年月、公司代號、公司名稱、產業別、營業收入-當月營收、營業收入-上月營收、營業收入-去年當月營收、營業收入-上月比較增減(%)、營業收入-去年同月增減(%)、累計營業收入-當月累計營收、累計營業收入-去年累計營收、累計營業收入-前期比較增減(%)、備註

### t187ap06_L_basi
- 說明：上市公司綜合損益表(金融業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_L_basi
- 欄位（25）：出表日期、年度、季別、公司代號、公司名稱、利息淨收益、利息以外淨損益、呆帳費用、承諾及保證責任準備提存、營業費用、繼續營業單位稅前淨利（淨損）、所得稅費用（利益）、繼續營業單位本期淨利（淨損）、停業單位損益、合併前非屬共同控制股權損益、本期淨利（淨損）、其他綜合損益（稅後）、合併前非屬共同控制股權綜合損益淨額、本期綜合損益總額（稅後）、淨利（損）歸屬於母公司業主、淨利（損）歸屬於共同控制下前手權益、淨利（損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_L_bd
- 說明：上市公司綜合損益表(證券期貨業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_L_bd
- 欄位（25）：出表日期、年度、季別、公司代號、公司名稱、收益、支出及費用、營業利益、營業外損益、稅前淨利（淨損）、所得稅費用（利益）、繼續營業單位本期淨利（淨損）、停業單位損益、合併前非屬共同控制股權損益、本期淨利（淨損）、本期其他綜合損益（稅後淨額）、合併前非屬共同控制股權綜合損益淨額、本期綜合損益總額、淨利（損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_L_ci
- 說明：上市公司綜合損益表(一般業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci
- 實測：實測可用（當期申報批次）
- 欄位（33）：出表日期、年度、季別、公司代號、公司名稱、營業收入、營業成本、原始認列生物資產及農產品之利益（損失）、生物資產當期公允價值減出售成本之變動利益（損失）、營業毛利（毛損）、未實現銷貨（損）益、已實現銷貨（損）益、營業毛利（毛損）淨額、營業費用、其他收益及費損淨額、營業利益（損失）、營業外收入及支出、稅前淨利（淨損）、所得稅費用（利益）、繼續營業單位本期淨利（淨損）、停業單位損益、合併前非屬共同控制股權損益、本期淨利（淨損）、其他綜合損益（淨額）、合併前非屬共同控制股權綜合損益淨額、本期綜合損益總額、淨利（淨損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（淨損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_L_fh
- 說明：上市公司綜合損益表(金控業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_L_fh
- 欄位（25）：出表日期、年度、季別、公司代號、公司名稱、利息淨收益、其他收益及費損淨額、利息以外淨收益、淨收益、呆帳費用、承諾及保證責任準備提存、保險負債準備淨變動、營業費用、繼續營業單位稅前損益、繼續營業單位本期淨利（淨損）、停業單位損益、本期稅後淨利（淨損）、本期其他綜合損益（稅後淨額）、本期綜合損益總額、淨利（淨損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（淨損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_L_ins
- 說明：上市公司綜合損益表(保險業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ins
- 欄位（26）：出表日期、年度、季別、公司代號、公司名稱、營業收入、營業成本、營業費用、營業利益（損失）、營業外收入及支出、繼續營業單位稅前純益（純損）、所得稅費用（利益）、繼續營業單位本期純益（純損）、停業單位損益、合併前非屬共同控制股權損益、本期淨利（淨損）、其他綜合損益（淨額）、合併前非屬共同控制股權綜合損益淨額、本期綜合損益總額、淨利（淨損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（淨損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_L_mim
- 說明：上市公司綜合損益表(異業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_L_mim
- 欄位（21）：出表日期、年度、季別、公司代號、公司名稱、收入、支出、繼續營業單位稅前淨利（淨損）、所得稅費用（利益）、繼續營業單位本期淨利（淨損）、停業單位損益、本期淨利（淨損）、其他綜合損益、本期綜合損益總額、淨利（淨損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（淨損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_X_basi
- 說明：公發公司綜合損益表-金融業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_X_basi
- 欄位（25）：出表日期、年度、季別、公司代號、公司名稱、利息淨收益、利息以外淨損益、呆帳費用、承諾及保證責任準備提存、營業費用、繼續營業單位稅前淨利（淨損）、所得稅費用（利益）、繼續營業單位本期稅後淨利（淨損）、停業單位損益、合併前非屬共同控制股權損益、本期稅後淨利（淨損）、其他綜合損益（稅後）、合併前非屬共同控制股權綜合損益淨額、本期綜合損益總額（稅後）、淨利（損）歸屬於母公司業主、淨利（損）歸屬於共同控制下前手權益、淨利（損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_X_bd
- 說明：公發公司綜合損益表-證券期貨業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_X_bd
- 欄位（25）：出表日期、年度、季別、公司代號、公司名稱、收益、支出及費用、營業利益、營業外損益、稅前淨利（淨損）、所得稅費用（利益）、繼續營業單位本期淨利（淨損）、停業單位損益、合併前非屬共同控制股權損益、本期淨利（淨損）、本期其他綜合損益（稅後淨額）、合併前非屬共同控制股權綜合損益淨額、本期綜合損益總額、淨利（損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_X_ci
- 說明：公發公司綜合損益表-一般業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_X_ci
- 欄位（33）：出表日期、年度、季別、公司代號、公司名稱、營業收入、營業成本、原始認列生物資產及農產品之利益（損失）、生物資產當期公允價值減出售成本之變動利益（損失）、營業毛利（毛損）、未實現銷貨（損）益、已實現銷貨（損）益、營業毛利（毛損）淨額、營業費用、其他收益及費損淨額、營業利益（損失）、營業外收入及支出、稅前淨利（淨損）、所得稅費用（利益）、繼續營業單位本期淨利（淨損）、停業單位損益、合併前非屬共同控制股權損益、本期淨利（淨損）、其他綜合損益（淨額）、合併前非屬共同控制股權綜合損益淨額、本期綜合損益總額、淨利（淨損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（淨損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_X_fh
- 說明：公發公司綜合損益表-金控業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_X_fh
- 欄位（25）：出表日期、年度、季別、公司代號、公司名稱、利息淨收益、利息以外淨收益、淨收益、呆帳費用、承諾及保證責任準備提存、保險負債準備淨變動、營業費用、繼續營業單位稅前損益、所得稅（費用）利益、繼續營業單位本期淨利（淨損）、停業單位損益、本期稅後淨利（淨損）、本期其他綜合損益（稅後淨額）、本期綜合損益總額、淨利（淨損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（淨損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_X_ins
- 說明：公發公司綜合損益表-保險業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_X_ins
- 欄位（26）：出表日期、年度、季別、公司代號、公司名稱、營業收入、營業成本、營業費用、營業利益（損失）、營業外收入及支出、繼續營業單位稅前純益（純損）、所得稅費用（利益）、繼續營業單位本期純益（純損）、停業單位損益、合併前非屬共同控制股權損益、本期淨利（淨損）、其他綜合損益（稅後淨額）、合併前非屬共同控制股權綜合損益淨額、本期綜合損益總額、淨利（淨損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（淨損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap06_X_mim
- 說明：公發公司綜合損益表-異業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap06_X_mim
- 欄位（21）：出表日期、年度、季別、公司代號、公司名稱、收入、支出、繼續營業單位稅前淨利（淨損）、所得稅費用（利益）、繼續營業單位本期淨利（淨損）、停業單位損益、本期淨利（淨損）、其他綜合損益、本期綜合損益總額、淨利（淨損）歸屬於母公司業主、淨利（淨損）歸屬於共同控制下前手權益、淨利（淨損）歸屬於非控制權益、綜合損益總額歸屬於母公司業主、綜合損益總額歸屬於共同控制下前手權益、綜合損益總額歸屬於非控制權益、基本每股盈餘（元）

### t187ap07_L_basi
- 說明：上市公司資產負債表(金融業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_L_basi
- 欄位（64）：出表日期、年度、季別、公司代號、公司名稱、現金及約當現金、存放央行及拆借銀行同業、透過損益按公允價值衡量之金融資產、透過其他綜合損益按公允價值衡量之金融資產、按攤銷後成本衡量之債務工具投資、避險之金融資產－淨額、附賣回票券及債券投資淨額、應收款項－淨額、當期所得稅資產、待出售資產－淨額、待分配予業主之資產－淨額、貼現及放款－淨額、採用權益法之投資－淨額、受限制資產－淨額、其他金融資產－淨額、保險合約資產、再保險合約資產、不動產及設備－淨額、使用權資產－淨額、投資性不動產－淨額、無形資產－淨額、遞延所得稅資產、其他資產－淨額、資產總額、央行及銀行同業存款、央行及同業融資、透過損益按公允價值衡量之金融負債、避險之衍生金融負債－淨額、附買回票券及債券負債、應付款項、當期所得稅負債、與待出售資產直接相關之負債、存款及匯款、應付金融債券、應付公司債、特別股負債、其他金融負債、負債準備、保險合約負債、再保險合約負債、租賃負債、遞延所得稅負債、其他負債、負債總額、股本、權益─具證券性質之虛擬通貨、資本公積、保留盈餘、其他權益、庫藏股票、歸屬於母公司業主之權益合計、共同控制下前手權益、合併前非屬共同控制股權、非控制權益、權益總額、待註銷股本股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、每股參考淨值

### t187ap07_L_bd
- 說明：上市公司資產負債表(證券期貨業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_L_bd
- 欄位（26）：出表日期、年度、季別、公司代號、公司名稱、流動資產、非流動資產、資產總計、流動負債、非流動負債、負債總計、股本、權益－具證券性質之虛擬通貨、資本公積、保留盈餘（或累積虧損）、其他權益、庫藏股票、歸屬於母公司業主權益合計、共同控制下前手權益、合併前非屬共同控制股權、非控制權益、權益總計、待註銷股本股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、母公司暨子公司持有之母公司庫藏股股數（單位：股）、每股參考淨值

### t187ap07_L_ci
- 說明：上市公司資產負債表(一般業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci
- 實測：實測可用（當期申報批次）
- 欄位（26）：出表日期、年度、季別、公司代號、公司名稱、流動資產、非流動資產、資產總計、流動負債、非流動負債、負債總計、股本、權益─具證券性質之虛擬通貨、資本公積、保留盈餘、其他權益、庫藏股票、歸屬於母公司業主之權益合計、共同控制下前手權益、合併前非屬共同控制股權、非控制權益、權益總計、待註銷股本股數、預收股款（權益項下）之約當發行股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、每股參考淨值

### t187ap07_L_fh
- 說明：上市公司資產負債表(金控業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_L_fh
- 欄位（61）：出表日期、年度、季別、公司代號、公司名稱、現金及約當現金、存放央行及拆借金融同業、透過損益按公允價值衡量之金融資產、透過其他綜合損益按公允價值衡量之金融資產、按攤銷後成本衡量之債務工具投資、避險之金融資產、附賣回票券及債券投資、應收款項－淨額、當期所得稅資產、待出售資產－淨額、待分配予業主之資產－淨額、貼現及放款－淨額、保險合約資產及再保險合約資產－淨額、採用權益法之投資－淨額、受限制資產－淨額、其他金融資產－淨額、投資性不動產－淨額、不動產及設備－淨額、使用權資產－淨額、無形資產－淨額、遞延所得稅資產、其他資產－淨額、資產總額、央行及金融同業存款、央行及同業融資、透過損益按公允價值衡量之金融負債、避險之衍生金融負債、附買回票券及債券負債、應付商業本票－淨額、應付款項、當期所得稅負債、與待出售資產直接相關之負債、存款及匯款、應付債券、其他借款、特別股負債、負債準備、其他金融負債、保險合約負債及再保險合約負債、租賃負債、遞延所得稅負債、其他負債、負債總額、股本、資本公積、保留盈餘、其他權益、庫藏股票、共同控制下前手權益、歸屬於母公司業主之權益、非控制權益、權益總額、待註銷股本股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、每股參考淨值

### t187ap07_L_ins
- 說明：上市公司資產負債表(保險業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ins
- 欄位（57）：出表日期、年度、季別、公司代號、公司名稱、現金及約當現金、應收款項、本期所得稅資產、待出售資產、待分配予業主之資產（或處分群組）、透過損益按公允價值衡量之金融資產、透過其他綜合損益按公允價值衡量之金融資產、按攤銷後成本衡量之金融資產、避險之金融資產、採用權益法之投資－淨額、其他金融資產－淨額、投資性不動產、放款、保險合約資產、再保險合約資產、不動產及設備、使用權資產、無形資產、遞延所得稅資產、其他資產、分離帳戶保險商品資產、資產總計、短期債務、應付款項、本期所得稅負債、與待出售資產直接相關之負債、透過損益按公允價值衡量之金融負債、避險之衍生金融負債、應付債券、特別股負債、其他金融負債、租賃負債、負債準備、遞延所得稅負債、其他負債、負債總計、股本、權益─具證券性質之虛擬通貨、資本公積、保留盈餘、其他權益、庫藏股票、歸屬於母公司業主之權益合計、共同控制下前手權益、合併前非屬共同控制股權、非控制權益、權益總計、負債及權益總計、待註銷股本股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、每股參考淨值

### t187ap07_L_mim
- 說明：上市公司資產負債表(異業)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_L_mim
- 欄位（25）：出表日期、年度、季別、公司代號、公司名稱、流動資產、非流動資產、資產總額、流動負債、非流動負債、負債總額、股本、權益－具證券性質之虛擬通貨、資本公積、保留盈餘、其他權益、庫藏股票、歸屬於母公司業主之權益合計、共同控制下前手權益、非控制權益、權益總額、待註銷股本股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、每股參考淨值

### t187ap07_X_basi
- 說明：公發公司資產負債表-金融業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_X_basi
- 欄位（64）：出表日期、年度、季別、公司代號、公司名稱、現金及約當現金、存放央行及拆借銀行同業、透過損益按公允價值衡量之金融資產、透過其他綜合損益按公允價值衡量之金融資產、按攤銷後成本衡量之債務工具投資、避險之衍生金融資產淨額、附賣回票券及債券投資淨額、應收款項－淨額、當期所得稅資產、待出售資產－淨額、待分配予業主之資產－淨額、貼現及放款－淨額、採用權益法之投資－淨額、受限制資產－淨額、其他金融資產－淨額、保險合約資產、再保險合約資產、不動產及設備－淨額、使用權資產－淨額、投資性不動產投資－淨額、無形資產－淨額、遞延所得稅資產、其他資產－淨額、資產總額、央行及銀行同業存款、央行及同業融資、透過損益按公允價值衡量之金融負債、避險之衍生金融負債－淨額、附買回票券及債券負債、應付款項、當期所得稅負債、與待出售資產直接相關之負債、存款及匯款、應付金融債券、應付公司債、特別股負債、其他金融負債、負債準備、保險合約負債、再保險合約負債、租賃負債、遞延所得稅負債、其他負債、負債總額、股本、權益─具證券性質之虛擬通貨、資本公積、保留盈餘、其他權益、庫藏股票、歸屬於母公司業主之權益合計、共同控制下前手權益、合併前非屬共同控制股權、非控制權益、權益總額、待註銷股本股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、每股參考淨值

### t187ap07_X_bd
- 說明：公發公司資產負債表-證券期貨業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_X_bd
- 欄位（26）：出表日期、年度、季別、公司代號、公司名稱、流動資產、非流動資產、資產總計、流動負債、非流動負債、負債總計、股本、權益－具證券性質之虛擬通貨、資本公積、保留盈餘（或累積虧損）、其他權益、庫藏股票、歸屬於母公司業主權益合計、共同控制下前手權益、合併前非屬共同控制股權、非控制權益、權益總計、待註銷股本股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、母公司暨子公司持有之母公司庫藏股股數（單位：股）、每股參考淨值

### t187ap07_X_ci
- 說明：公發公司資產負債表-一般業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_X_ci
- 欄位（26）：出表日期、年度、季別、公司代號、公司名稱、流動資產、非流動資產、資產總計、流動負債、非流動負債、負債總計、股本、權益─具證券性質之虛擬通貨、資本公積、保留盈餘、其他權益、庫藏股票、歸屬於母公司業主之權益合計、共同控制下前手權益、合併前非屬共同控制股權、非控制權益、權益總計、待註銷股本股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、每股參考淨值

### t187ap07_X_fh
- 說明：公發公司資產負債表-金控業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_X_fh
- 欄位（61）：出表日期、年度、季別、公司代號、公司名稱、現金及約當現金、存放央行及拆借金融同業、透過損益按公允價值衡量之金融資產、透過其他綜合損益按公允價值衡量之金融資產、按攤銷後成本衡量之債務工具投資、避險之衍生金融資產、附賣回票券及債券投資、應收款項－淨額、當期所得稅資產、待出售資產－淨額、待分配予業主之資產－淨額、貼現及放款－淨額、保險合約資產及再保險合約資產－淨額、採用權益法之投資－淨額、受限制資產－淨額、其他金融資產－淨額、投資性不動產－淨額、不動產及設備－淨額、使用權資產－淨額、無形資產－淨額、遞延所得稅資產、其他資產－淨額、資產總額、央行及金融同業存款、央行及同業融資、透過損益按公允價值衡量之金融負債、避險之衍生金融負債、附買回票券及債券負債、應付商業本票－淨額、應付款項、當期所得稅負債、與待出售資產直接相關之負債、存款及匯款、應付債券、其他借款、特別股負債、負債準備、其他金融負債、保險合約負債及再保險合約負債、租賃負債、遞延所得稅負債、其他負債、負債總額、股本、資本公積、保留盈餘、其他權益、庫藏股票、共同控制下前手權益、歸屬於母公司業主之權益、非控制權益、權益總額、待註銷股本股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、每股參考淨值

### t187ap07_X_ins
- 說明：公發公司資產負債表-保險業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_X_ins
- 欄位（57）：出表日期、年度、季別、公司代號、公司名稱、現金及約當現金、應收款項、本期所得稅資產、待出售資產、待分配予業主之資產（或處分群組）、透過損益按公允價值衡量之金融資產、透過其他綜合損益按公允價值衡量之金融資產、按攤銷後成本衡量之金融資產、避險之金融資產、採用權益法之投資－淨額、其他金融資產－淨額、投資性不動產、放款、保險合約資產、再保險合約資產、不動產及設備、使用權資產、無形資產、遞延所得稅資產、其他資產、分離帳戶保險商品資產、資產總計、短期債務、應付款項、本期所得稅負債、與待出售資產直接相關之負債、透過損益按公允價值衡量之金融負債、避險之金融負債、應付債券、特別股負債、其他金融負債、租賃負債、負債準備、遞延所得稅負債、其他負債、負債總計、股本、權益─具證券性質之虛擬通貨、資本公積、保留盈餘、其他權益、庫藏股票、歸屬於母公司業主之權益合計、共同控制下前手權益、合併前非屬共同控制股權、非控制權益、權益總計、負債及權益總計、待註銷股本股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、每股參考淨值

### t187ap07_X_mim
- 說明：公發公司資產負債表-異業
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap07_X_mim
- 欄位（25）：出表日期、年度、季別、公司代號、公司名稱、流動資產、非流動資產、資產總計、流動負債、非流動負債、負債總計、股本、權益－具證券性質之虛擬通貨、資本公積、保留盈餘、其他權益、庫藏股票、歸屬於母公司業主之權益合計、共同控制下前手權益、非控制權益、權益總額、待註銷股本股數（單位：股）、預收股款（權益項下）之約當發行股數（單位：股）、母公司暨子公司所持有之母公司庫藏股股數（單位：股）、每股參考淨值

### t187ap11_P
- 說明：公發公司董監事持股餘額明細
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap11_P
- 欄位（13）：出表日期、資料年月、公司代號、公司名稱、職稱、姓名、選任時持股、目前持股、設質股數、設質股數佔持股比例、內部人關係人目前持股合計、內部人關係人設質股數、內部人關係人設質比例

### t187ap15_L
- 說明：上市公司截至各季綜合損益財測達成情形(簡式)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap15_L
- 欄位（9）：出表日期、年度、季別、公司代號、公司名稱、財測序號、涵蓋期間、截至該季經會計師查核或核閱數、截至該季綜合損益預測數

### t187ap16_L
- 說明：上市公司當季綜合損益經會計師查核(核閱)數與當季預測數差異達百分之十以上者，或截至當季累計差異達百分之二十以上者(簡式)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap16_L
- 欄位（11）：出表日期、年度、季別、公司代號、公司名稱、財測序號、涵蓋期間、當季經會計師查核或核閱數、截至當季經會計師查核或核閱數、當季稅前(綜合)損益預測數、截至當季稅前(綜合)損益預測數

### t187ap17_L
- 說明：上市公司營益分析查詢彙總表(全體公司彙總報表)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap17_L
- 欄位（10）：出表日期、年度、季別、公司代號、公司名稱、營業收入(百萬元)、毛利率(%)(營業毛利)/(營業收入)、營業利益率(%)(營業利益)/(營業收入)、稅前純益率(%)(稅前純益)/(營業收入)、稅後純益率(%)(稅後純益)/(營業收入)

### t187ap31_L
- 說明：上市公司財務報告經監察人承認情形
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap31_L
- 欄位（6）：出表日期、公司代號、公司名稱、是否設置審計委員會、出具本次財務報告審查報告書之監察人姓名、監察人實際在任席次

## 證券交易（36 個）

### BFI84U
- 說明：集中市場停資停券預告表
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/BFI84U
- 欄位（5）：Code、Name、StartDate、EndDate、Reason

### BFIAUU_d
- 說明：集中市場鉅額交易日成交量值統計
- 網址：https://openapi.twse.com.tw/v1/block/BFIAUU_d
- 欄位（6）：Date、Class、Type、TradeVolume、MarketSharePer、TradeValue

### BFIAUU_m
- 說明：集中市場鉅額交易月成交量值統計
- 網址：https://openapi.twse.com.tw/v1/block/BFIAUU_m
- 欄位（5）：Month、Class、TradeVolume、MarketSharePer、TradeValue

### BFIAUU_y
- 說明：集中市場鉅額交易年成交量值統計
- 網址：https://openapi.twse.com.tw/v1/block/BFIAUU_y
- 欄位（4）：Month、TradeVolume、MarketSharePer、TradeValue

### BFT41U
- 說明：集中市場盤後定價交易
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/BFT41U
- 欄位（8）：Code、Name、TradeVolume、Transaction、TradeValue、TradePrice、BidVolume、AskVolume

### BFZFZU_T
- 說明：投資理財節目異常推介個股
- 網址：https://openapi.twse.com.tw/v1/Announcement/BFZFZU_T
- 欄位（4）：Number、Code、Name、Date

### BWIBBU_ALL
- 說明：上市個股日本益比、殖利率及股價淨值比（依代碼查詢）
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL
- 實測：實測可用（PE/PB/殖利率）
- 欄位（6）：Date、Code、Name、PEratio、DividendYield、PBratio

### BWIBBU_d
- 說明：上市個股日本益比、殖利率及股價淨值比（依日期查詢）
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d
- 欄位（9）：Date、Code、Name、ClosePrice、DividendYield、DividendYear、PEratio、PBratio、FiscalYearQuarter

### FMNPTK_ALL
- 說明：上市個股年成交資訊
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/FMNPTK_ALL
- 欄位（11）：Year、Code、Name、TradeVolume、TradeValue、Transaction、HighestPrice、HDate、LowestPrice、LDate、AvgClosingPrice

### FMSRFK_ALL
- 說明：上市個股月成交資訊
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/FMSRFK_ALL
- 欄位（10）：Month、Code、Name、HighestPrice、LowestPrice、WeightedAvgPriceAB、Transaction、TradeValueA、TradeVolumeB、TurnoverRatio

### FMTQIK
- 說明：集中市場每日市場成交資訊
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK
- 欄位（6）：Date、TradeVolume、TradeValue、Transaction、TAIEX、Change

### MI_5MINS
- 說明：每 5 秒委託成交統計
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/MI_5MINS
- 欄位（8）：Time、AccBidOrders、AccBidVolume、AccAskOrders、AccAskVolume、AccTransaction、AccTradeVolume、AccTradeValue

### MI_INDEX
- 說明：每日收盤行情-大盤統計資訊
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX
- 欄位（7）：日期、指數、收盤指數、漲跌、漲跌點數、漲跌百分比、特殊處理註記

### MI_INDEX20
- 說明：集中市場每日成交量前二十名證券
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX20
- 欄位（14）：Date、Rank、Code、Name、TradeVolume、Transaction、OpeningPrice、HighestPrice、LowestPrice、ClosingPrice、Dir、Change、LastBestBidPrice、LastBestAskPrice

### MI_MARGN
- 說明：集中市場融資融券餘額
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN
- 欄位（16）：股票代號、股票名稱、融資買進、融資賣出、融資現金償還、融資前日餘額、融資今日餘額、融資限額、融券買進、融券賣出、融券現券償還、融券前日餘額、融券今日餘額、融券限額、資券互抵、註記

### MI_QFIIS_cat
- 說明：集中市場外資及陸資投資類股持股比率表
- 網址：https://openapi.twse.com.tw/v1/fund/MI_QFIIS_cat
- 欄位（5）：IndustryCat、Numbers、ShareNumber、ForeignMainlandAreaShare、Percentage

### MI_QFIIS_sort_20
- 說明：集中市場外資及陸資持股前 20 名彙總表
- 網址：https://openapi.twse.com.tw/v1/fund/MI_QFIIS_sort_20
- 欄位（9）：Rank、Code、Name、ShareNumber、AvailableShare、SharesHeld、AvailableInvestPer、SharesHeldPer、Upperlimit

### STOCK_DAY_ALL
- 說明：上市個股日成交資訊
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
- 實測：實測可用；僅發布 T-1/T-2 收盤
- 欄位（11）：Date、Code、Name、TradeVolume、TradeValue、OpeningPrice、HighestPrice、LowestPrice、ClosingPrice、Change、Transaction

### STOCK_DAY_AVG_ALL
- 說明：上市個股日收盤價及月平均價
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL
- 欄位（5）：Date、Code、Name、ClosingPrice、MonthlyAveragePrice

### STOCK_FIRST
- 說明：每日第一上市外國股票成交量值
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/STOCK_FIRST
- 欄位（16）：Code、Name、TradeVolume、Transaction、TradeValue、OpeningPrice、HighestPrice、LowestPrice、ClosingPrice、Dir、Change、LastBestBidPrice、LastBestBidVolume、LastBestAskPrice、LastBestAskVolume、PriceEarningRatio

### TWT48U_ALL
- 說明：上市股票除權除息預告表
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL
- 欄位（12）：Date、Code、Name、Exdividend、StockDividendRatio、SubscriptionRatio、SubscriptionPricePerShare、CashDividend、SharesOffered、SharesEmpOwner、SharesholderOwner、StockHoldingRatio

### TWT53U
- 說明：集中市場零股交易行情單
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/TWT53U
- 欄位（10）：Code、Name、TradeVolume、Transaction、TradeValue、TradePrice、BestBidPrice、BestBidVolume、BestAskPrice、BestAskVolume

### TWT84U
- 說明：上市個股股價升降幅度
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/TWT84U
- 欄位（11）：Code、Name、TodayLimitUp、TodayOpeningRefPrice、TodayLimitDown、PreviousDayOpeningRefPrice、PreviousDayPrice、PreviousDayLimitUp、PreviousDayLimitDown、LastTradingDay、AllowOddLotTrade

### TWT85U
- 說明：集中市場證券變更交易
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/TWT85U
- 欄位（3）：Code、Name、PeriodicCallAuctionTrading

### TWT88U
- 說明：上市個股首五日無漲跌幅
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/TWT88U
- 欄位（12）：SecurCode、SecurName、1stTradingDate、5thTradingDate、PriceUnderwritten、OverAllotmentShares、Code、Name、BuySell、TradingPrice、TradingVolume、AccTradingVolume

### TWT96U
- 說明：上市上櫃股票當日可借券賣出股數
- 網址：https://openapi.twse.com.tw/v1/SBL/TWT96U
- 欄位（4）：TWSECode、TWSEAvailableVolume、GRETAICode、GRETAIAvailableVolume

### TWTAWU
- 說明：集中市場暫停交易證券
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/TWTAWU
- 欄位（7）：Number、Code、Name、TradingHaltDate、TradingHaltTime、TradingResumptionDate、TradingResumptionTime

### TWTB4U
- 說明：上市股票每日當日沖銷交易標的及統計
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/TWTB4U
- 欄位（4）：Date、Code、Name、Suspension

### TWTBAU1
- 說明：集中市場暫停先賣後買當日沖銷交易標的預告表
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/TWTBAU1
- 欄位（5）：Code、Name、StartDate、EndDate、Reason

### TWTBAU2
- 說明：集中市場暫停先賣後買當日沖銷交易歷史查詢
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/TWTBAU2
- 欄位（5）：Code、Name、StartDate、EndDate、Reason

### holidaySchedule
- 說明：有價證券集中交易市場開（休）市日期
- 網址：https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule
- 欄位（4）：Name、Date、Weekday、Description

### notetrans
- 說明：集中市場公布注意累計次數可能達處置標準資訊
- 網址：https://openapi.twse.com.tw/v1/announcement/notetrans
- 欄位（3）：Code、Name、RecentlyMetAttentionSecuritiesCriteria

### notice
- 說明：集中市場當日公布注意股票
- 網址：https://openapi.twse.com.tw/v1/announcement/notice
- 欄位（8）：Number、Code、Name、NumberOfAnnouncement、TradingInfoForAttention、Date、ClosingPrice、PE

### t187ap19
- 說明：電子式交易統計資訊
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap19
- 欄位（20）：出表日期、成交月份、本月新增戶數、本月註銷戶數、累計開戶數、本月交易戶數、本月交易人數、委託筆數、委託金額、成交筆數、成交金額、平均每筆成交金額、公司總成交筆數、公司總成交金額、占公司成交比率(筆數)、占公司成交比率(金額)、市場成交總筆數(買賣合計)、市場成交總金額(買賣合計)、占市場成交比率(筆數)、占市場成交比率(金額)

### t187ap37_L
- 說明：上市權證基本資料彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap37_L
- 欄位（20）：出表日期、權證代號、權證簡稱、權證類型、類別、流動量提供者報價方式、履約開始日、最後交易日、履約截止日、發行單位數量(仟單位)、結算方式(詳附註編號說明)、標的證券/指數、最新標的履約配發數量(每仟單位權證)、原始履約價格(元)/履約指數、原始上限價格(元)/上限指數、原始下限價格(元)/下限指數、最新履約價格(元)/履約指數、最新上限價格(元)/上限指數、最新下限價格(元)/下限指數、備註

### twtazu_od
- 說明：集中市場漲跌證券數統計表
- 網址：https://openapi.twse.com.tw/v1/opendata/twtazu_od
- 欄位（9）：出表日期、類型、上漲、漲停、下跌、跌停、持平、未成交、無比價

## 公司治理（56 個）

### applylistingForeign
- 說明：外國公司向證交所申請第一上市之公司
- 網址：https://openapi.twse.com.tw/v1/company/applylistingForeign
- 欄位（13）：No、Code、Company、ApplicationDate、Chairman、AmountofCapital 、CommitteeDate、ApprovedDate、AgreementDate、ListingDate、Underwriter、UnderwritingPrice、Note

### applylistingLocal
- 說明：申請上市之本國公司
- 網址：https://openapi.twse.com.tw/v1/company/applylistingLocal
- 欄位（13）：Code、Company、ApplicationDate、Chairman、AmountofCapital 、CommitteeDate、ApprovedDate、AgreementDate、ListingDate、ApprovedListingDate、Underwriter、UnderwritingPrice、Note

### newlisting
- 說明：最近上市公司
- 網址：https://openapi.twse.com.tw/v1/company/newlisting
- 欄位（13）：Code、Company、ApplicationDate、Chairman、AmountofCapital 、CommitteeDate、ApprovedDate、AgreementDate、ListingDate、ApprovedListingDate、Underwriter、UnderwritingPrice、Note

### punish
- 說明：集中市場公布處置股票
- 網址：https://openapi.twse.com.tw/v1/announcement/punish
- 欄位（10）：Number、Date、Code、Name、NumberOfAnnouncement、ReasonsOfDisposition、DispositionPeriod、DispositionMeasures、Detail、LinkInformation

### suspendListingCsvAndHtml
- 說明：終止上市公司
- 網址：https://openapi.twse.com.tw/v1/company/suspendListingCsvAndHtml
- 欄位（3）：DelistingDate、Company、Code

### t187ap02_L
- 說明：上市公司持股逾 10% 大股東名單
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap02_L
- 欄位（4）：出表日期、公司代號、公司名稱、大股東名稱

### t187ap03_L
- 說明：上市公司基本資料
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap03_L
- 實測：實測可用（1,099 家）
- 欄位（33）：出表日期、公司代號、公司名稱、公司簡稱、外國企業註冊地國、產業別、住址、營利事業統一編號、董事長、總經理、發言人、發言人職稱、代理發言人、總機電話、成立日期、上市日期、普通股每股面額、實收資本額、私募股數、特別股、編制財務報表類型、股票過戶機構、過戶電話、過戶地址、簽證會計師事務所、簽證會計師1、簽證會計師2、英文簡稱、英文通訊地址、傳真機號碼、電子郵件信箱、網址、已發行普通股數或TDR原股發行股數

### t187ap03_P
- 說明：公開發行公司基本資料
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap03_P
- 欄位（33）：出表日期、公司代號、公司名稱、公司簡稱、外國企業註冊地國、產業別、住址、營利事業統一編號、董事長、總經理、發言人、發言人職稱、代理發言人、總機電話、成立日期、上市日期、普通股每股面額、實收資本額、私募股數、特別股、編制財務報表類型、股票過戶機構、過戶電話、過戶地址、簽證會計師事務所、簽證會計師1、簽證會計師2、英文簡稱、英文通訊地址、傳真機號碼、電子郵件信箱、網址、已發行普通股數或TDR原股發行股數

### t187ap04_L
- 說明：上市公司每日重大訊息
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap04_L
- 欄位（9）：出表日期、發言日期、發言時間、公司代號、公司名稱、主旨 、符合條款、事實發生日、說明

### t187ap05_P
- 說明：公開發行公司每月營業收入彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap05_P
- 欄位（14）：出表日期、資料年月、公司代號、公司名稱、產業別、營業收入-當月營收、營業收入-上月營收、營業收入-去年當月營收、營業收入-上月比較增減(%)、營業收入-去年同月增減(%)、累計營業收入-當月累計營收、累計營業收入-去年累計營收、累計營業收入-前期比較增減(%)、備註

### t187ap08_L
- 說明：上市公司董事、監察人持股不足法定成數彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap08_L
- 欄位（15）：出表日期、公司代號、公司名稱、已發行股份總額、全體董事應持有股數、全體董事本人實際持有股數、全體董事法人代表人分戶集保股數、全體董事保留運用決定權信託股數、全體董事不足股數、全體監察人應持有股數、全體監察人本人實際持有股數、全體監察人法人代表人分戶集保股數、全體監察人保留運用決定權信託股數、全體監察人不足股數、持股不足已通知其董監

### t187ap09_L
- 說明：上市公司董事、監察人質權設定占董事及監察人實際持有股數彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap09_L
- 欄位（3）：出表日期、百分比、公司名稱

### t187ap10_L
- 說明：上市公司董事、監察人持股不足法定成數連續達3個月以上彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap10_L
- 欄位（12）：出表日期、連續不足達3個月、連續不足達4個月、連續不足達5個月、連續不足達6個月、連續不足達7個月、連續不足達8個月、連續不足達9個月、連續不足達10個月、連續不足達11個月、連續不足達12個月、連續不足逾1年以上

### t187ap11_L
- 說明：上市公司董監事持股餘額明細資料
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap11_L
- 欄位（13）：出表日期、資料年月、公司代號、公司名稱、職稱、姓名、選任時持股 、目前持股、設質股數、設質股數佔持股比例、內部人關係人目前持股合計、內部人關係人設質股數、內部人關係人設質比例

### t187ap12_L
- 說明：上市公司每日內部人持股轉讓事前申報表-持股轉讓日報表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap12_L
- 欄位（16）：出表日期、公司代號、公司名稱、申報人身分、姓名、預定轉讓方式及股數-轉讓方式、預定轉讓方式及股數-轉讓股數、每日於盤中交易最大得轉讓股數、受讓人、目前持有股數-自有持股、目前持有股數-保留運用決定權信託股數、預定轉讓總股數-自有持股、預定轉讓總股數-保留運用決定權信託股數、預定轉讓後持股-自有持股、預定轉讓後持股-保留運用決定權信託股數、有效轉讓期間

### t187ap13_L
- 說明：上市公司每日內部人持股轉讓事前申報表-持股未轉讓日報表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap13_L
- 欄位（12）：出表日期、公司代號、公司名稱、申報人身分、姓名、未轉讓股數-自有持股、未轉讓股數-保留運用決定權信託股數、目前持股-自有持股、目前持股-保留運用決定權信託股數、原申報預定轉讓股數-自有持股、原申報預定轉讓股數-保留運用決定權信託股數、未轉讓理由

### t187ap14_L
- 說明：上市公司各產業EPS統計資訊
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap14_L
- 欄位（12）：出表日期、年度、季別、公司代號、公司名稱、產業別、基本每股盈餘(元)、普通股每股面額、營業收入、營業利益、營業外收入及支出、稅後淨利

### t187ap22_L
- 說明：上市公司金管會證券期貨局裁罰案件專區
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap22_L
- 欄位（7）：出表日期、發函日期、股票代號、公司名稱、違規事由、違反法規、裁處情形

### t187ap23_L
- 說明：上市公司違反資訊申報、重大訊息及說明記者會規定專區
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap23_L
- 欄位（8）：出表日期、發函日期、股票代號、公司名稱、違規事由、違反資訊申報作業辦法條款、違反重大訊息之查證暨公開處理程序條款、裁罰金額(萬)

### t187ap24_L
- 說明：上市公司經營權及營業範圍異(變)動專區-經營權異動公司
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap24_L
- 欄位（5）：出表日期、公司代號、公司名稱、經營權異動日期、經營權異動說明

### t187ap25_L
- 說明：上市公司經營權及營業範圍異(變)動專區-營業範圍重大變更公司
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap25_L
- 欄位（7）：出表日期、序號、年度、季別、公司代號、公司名稱、營業範圍重大變更說明

### t187ap26_L
- 說明：上市公司經營權及營業範圍異(變)動專區-經營權異動且營業範圍重大變更停止買賣公司
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap26_L
- 欄位（4）：出表日期、公司代號、公司名稱、停止買賣開始日

### t187ap27_L
- 說明：上市公司經營權及營業範圍異(變)動專區-經營權異動且營業範圍重大變更列為變更交易公司
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap27_L
- 欄位（4）：出表日期、公司代號、公司名稱、變更交易開始日

### t187ap29_A_L
- 說明：上市公司董事酬金相關資訊
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap29_A_L
- 欄位（20）：出表日期、產業類別、公司代號、公司名稱、董事酬金-前年支付、董事酬金-今年支付、董事酬金-合計、董事酬金加計兼任員工酬金-前年支付、董事酬金加計兼任員工酬金-今年支付、加計兼任員工酬金-合計、酬金總額占稅後損益百分比(%)-董事酬金、酬金總額占稅後損益百分比(%)-加計兼任員工酬金、平均每位董事酬金-董事酬金、平均每位董事酬金-加計兼任員工酬金、領取來自子公司以外轉投資事業或母公司酬金、稅後純益、每股盈餘、股東權益報酬率(%)、實收資本額(仟元)、稅後損益與董監酬金變動之關聯性與合理性說明

### t187ap29_B_L
- 說明：上市公司監察人酬金相關資訊
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap29_B_L
- 欄位（15）：出表日期、產業類別、公司代號、公司名稱、監察人酬金-前年支付、監察人酬金-今年支付、監察人酬金-合計、酬金總額占稅後損益百分比(%)、平均每位監察人酬金、領取來自子公司以外轉投資事業或母公司酬金、稅後純益、每股盈餘、股東權益報酬率(%)、實收資本額(仟元)、稅後損益與董監酬金變動之關聯性與合理性說明

### t187ap29_C_L
- 說明：上市公司合併報表董事酬金相關資訊
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap29_C_L
- 欄位（20）：出表日期、產業類別、公司代號、公司名稱、董事酬金-前年支付、董事酬金-今年支付、董事酬金-合計、董事酬金加計兼任員工酬金-前年支付、董事酬金加計兼任員工酬金-今年支付、加計兼任員工酬金-合計、酬金總額占稅後損益百分比(%)-董事酬金、酬金總額占稅後損益百分比(%)-加計兼任員工酬金、平均每位董事酬金-董事酬金、平均每位董事酬金-加計兼任員工酬金、領取來自子公司以外轉投資事業或母公司酬金、稅後純益、每股盈餘、股東權益報酬率(%)、實收資本額(仟元)、稅後損益與董監酬金變動之關聯性與合理性說明

### t187ap29_D_L
- 說明：上市公司合併報表監察人酬金相關資訊
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap29_D_L
- 欄位（15）：出表日期、產業類別、公司代號、公司名稱、監察人酬金-前年支付、監察人酬金-今年支付、監察人酬金-合計、酬金總額占稅後損益百分比(%)、平均每位監察人酬金、領取來自子公司以外轉投資事業或母公司酬金、稅後純益、每股盈餘、股東權益報酬率(%)、實收資本額(仟元)、稅後損益與董監酬金變動之關聯性與合理性說明

### t187ap30_L
- 說明：上市公司獨立董監事兼任情形彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap30_L
- 欄位（12）：出表日期、序號、公司代號、公司名稱、職稱、姓名、就任日期、主要現職、主要經歷、目前兼任其他公司名稱、其他公司職稱、備註

### t187ap32_L
- 說明：上市公司公司治理之相關規程規則
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap32_L
- 欄位（4）：出表日期、公司代號、公司名稱、公司治理之相關規程規則

### t187ap33_L
- 說明：上市公司董事長是否兼任總經理
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap33_L
- 欄位（6）：出表日期、公司代號、公司名稱、董事長、總經理、董事長是否兼任總經理

### t187ap34_L
- 說明：上市公司採累積投票制、全額連記法、候選人提名制選任董監事及當選資料彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap34_L
- 欄位（13）：出表日期、公司代號、公司名稱、股東常(臨時)會日期-常或臨時、股東常(臨時)會日期-日期、是否選任董監事、董監事選任方式、是否採候選人提名制選任董監事、採候選人提名制選任董監事相關公告-提名受理期間、提名受理處所、候選人類別、候選人姓名、是否當選

### t187ap35_L
- 說明：上市公司股東行使提案權情形彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap35_L
- 欄位（7）：出表日期、公司代號、公司名稱、召開股東會日期、股東依公司法第172條之1行使提案權-提案受理期間、提案受理處所、提案內容

### t187ap38_L
- 說明：上市公司股東會公告-召集股東常(臨時)會公告資料彙總表(95年度起適用)
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap38_L
- 欄位（20）：出表日期、公司代號、公司名稱、股東常(臨時)會日期-常或臨時、股東常(臨時)會日期-日期、停止過戶起訖日期-起、停止過戶起訖日期-訖、預擬配發現金(股利)(元/股)-盈餘、預擬配發現金(股利)(元/股)-法定盈餘公積、資本公積、預擬配股(元/股)-盈餘、預擬配股(元/股)-法定盈餘公積、資本公積、擬現金增資金額(元)、現金增資認購率(%)、員工紅利-現金紅利(元)、員工紅利-股票紅利(股)、特別股股利(元/股)、董監酬勞(元)、公告日期、公告時間、種類

### t187ap41_L
- 說明：上市公司召開股東常 (臨時) 會日期、地點及採用電子投票情形等資料彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap41_L
- 欄位（12）：出表日期、公司代號、公司名稱、公司地址、股東常(臨時)會、開會日期、開會地點、是否改選董監、聯絡電話、股務單位、股務單位電話、是否採電子投票

### t187ap45_L
- 說明：上市公司股利分派情形
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap45_L
- 實測：實測可用（1,239 家）
- 欄位（24）：出表日期、公司代號、公司名稱、決議（擬議）進度、股利年度、股利所屬年(季)度、股利所屬期間、期別、董事會（擬議）股利分派日、股東會日期、期初未分配盈餘/待彌補虧損(元)、本期淨利(淨損)(元)、可分配盈餘(元)、分配後期末未分配盈餘(元)、股東配發-盈餘分配之現金股利(元/股)、股東配發-法定盈餘公積發放之現金(元/股)、股東配發-資本公積發放之現金(元/股)、股東配發-股東配發之現金(股利)總金額(元)、股東配發-盈餘轉增資配股(元/股)、股東配發-法定盈餘公積轉增資配股(元/股)、股東配發-資本公積轉增資配股(元/股)、股東配發-股東配股總股數(股)、摘錄公司章程-股利分派部分、備註

### t187ap46_L_1
- 說明：上市公司企業ESG資訊揭露彙總資料-溫室氣體排放
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_1
- 欄位（14）：出表日期、報告年度、公司代號、公司名稱、範疇一排放量(噸CO2e)、範疇一資料邊界、範疇一取得驗證、範疇二排放量(噸CO2e)、範疇二資料邊界、範疇二取得驗證、範疇三排放量(噸CO2e)、範疇三資料邊界、範疇三取得驗證、溫室氣體排放密集度(噸CO2e/單位)

### t187ap46_L_10
- 說明：上市公司企業ESG資訊揭露彙總資料-燃料管理
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_10
- 欄位（8）：出表日期、報告年度、公司代號、公司名稱、消耗燃料總量(十億焦耳(GJ))、煤炭百分比、天然氣百分比、再生燃料百分比

### t187ap46_L_11
- 說明：上市公司企業ESG資訊揭露彙總資料-產品生命週期
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_11
- 欄位（6）：出表日期、報告年度、公司代號、公司名稱、產品生命週期管理之揭露：報廢產品及電子廢棄物之重量(公噸(t))、產品生命週期管理之揭露：含報廢產品及電子廢棄物之再循環之百分比

### t187ap46_L_12
- 說明：上市公司企業ESG資訊揭露彙總資料-食品安全
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_12
- 欄位（12）：出表日期、報告年度、公司代號、公司名稱、為改善食品衛生、安全與品質，而針對其從業人員、作業場所、設施衛生管理及其品保制度等方面進行之評估與改進及所影響之百分比、違反有關產品與服務之健康與安全法規及未遵循產品與服務之資訊與標示法規之事件類別與次數、違反有關產品與服務之健康與安全法規及未遵循產品與服務之資訊與標示法規之產品下架次數(次)、違反有關產品與服務之健康與安全法規及未遵循產品與服務之資訊與標示法規之下架產品總重量(公噸(t))、經獨立第三方驗證符合國際認證之食品安全管理系統標準之廠房所生產產品之百分比、依法規要求或自願進行產品追溯與追蹤管理之相關產品占所有產品之百分比、依法規要求或自願設置食品安全實驗室之相關支出(仟元)、依法規要求或自願設置食品安全實驗室之相關支出占營業收入淨額之百分比

### t187ap46_L_13
- 說明：上市公司企業ESG資訊揭露彙總資料-供應鏈管理
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_13
- 欄位（7）：出表日期、報告年度、公司代號、公司名稱、採購符合國際認可之產品責任標準者占整體採購之百分比，並依標準區分、對供應商進行稽核之家數(家)、對供應商進行稽核之百分比

### t187ap46_L_14
- 說明：上市公司企業ESG資訊揭露彙總資料-產品品質與安全
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_14
- 欄位（7）：出表日期、報告年度、公司代號、公司名稱、售出產品重量(公噸(t))、生產設施場所數量(座)、依產品類別之產品產量

### t187ap46_L_15
- 說明：上市公司企業ESG資訊揭露彙總資料-社區關係
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_15
- 欄位（5）：出表日期、報告年度、公司代號、公司名稱、在人口密集地區的煉油廠數量(座)

### t187ap46_L_16
- 說明：上市公司企業ESG資訊揭露彙總資料-資訊安全
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_16
- 欄位（7）：出表日期、報告年度、公司代號、公司名稱、資訊外洩事件數量、與個資相關的資訊外洩事件占比、因資訊外洩事件而受影響的顧客數(人)

### t187ap46_L_17
- 說明：上市公司企業ESG資訊揭露彙總資料-普惠金融
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_17
- 欄位（7）：出表日期、報告年度、公司代號、公司名稱、對促進小型企業及社區發展的貸放件數(件)、對促進小型企業及社區發展的貸放餘額(仟元)、對缺少銀行服務之弱勢族群提供金融教育之參與人數(人)

### t187ap46_L_18
- 說明：上市公司企業ESG資訊揭露彙總資料-持股及控制力
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_18
- 欄位（5）：出表日期、報告年度、公司代號、公司名稱、前10大股東持股情形

### t187ap46_L_19
- 說明：上市公司企業ESG資訊揭露彙總資料-風險管理政策
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_19
- 欄位（6）：出表日期、報告年度、公司代號、公司名稱、重大事件之風險管理政策、與使用關鍵材料相關的風險管理之描述

### t187ap46_L_2
- 說明：上市公司企業ESG資訊揭露彙總資料-能源管理
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_2
- 欄位（7）：出表日期、報告年度、公司代號、公司名稱、使用率(再生能源/總能源)、資料範圍、取得驗證

### t187ap46_L_20
- 說明：上市公司企業ESG資訊揭露彙總資料-反競爭行為法律訴訟
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_20
- 欄位（5）：出表日期、報告年度、公司代號、公司名稱、因與反競爭行為條例相關的法律訴訟而造成的金錢損失總額(仟元)

### t187ap46_L_21
- 說明：上市公司企業ESG資訊揭露彙總資料-職業安全衛生
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_21
- 欄位（9）：出表日期、報告年度、公司代號、公司名稱、職業災害人數及比率-人數、職業災害人數及比率-比率、火災件數(件)、火災死傷人數(人)、火災死傷人數占員工總人數比率

### t187ap46_L_3
- 說明：上市公司企業ESG資訊揭露彙總資料-水資源管理
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_3
- 欄位（9）：出表日期、報告年度、公司代號、公司名稱、用水量(公噸)、資料範圍、用水密集度-密集度(公噸/單位) 、用水密集度-單位、取得驗證

### t187ap46_L_4
- 說明：上市公司企業ESG資訊揭露彙總資料-廢棄物管理
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_4
- 欄位（13）：出表日期、報告年度、公司代號、公司名稱、有害廢棄物量-數據(公噸) 、有害廢棄物量-資料範圍、非有害廢棄物量-數據(公噸)、非有害廢棄物量-資料範圍、總重量(有害+非有害)-數據(公噸)、總重量(有害+非有害)-資料範圍、廢棄物密集度-密集度(公噸/單位) 、廢棄物密集度-單位、取得驗證

### t187ap46_L_5
- 說明：上市公司企業ESG資訊揭露彙總資料-人力發展
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_5
- 欄位（14）：出表日期、報告年度、公司代號、公司名稱、員工福利平均數(仟元/人)、員工薪資平均數(仟元/人) 、非擔任主管職務之全時員工薪資平均數(仟元/人) 、非擔任主管職務之全時員工薪資平均數變動百分比、非擔任主管之全時員工薪資中位數(仟元/人) 、非擔任主管職務之全時員工薪資中位數變動百分比、管理職女性主管佔比、新進員工年齡分布、離職員工年齡分布、高齡員工晉用政策及培訓計畫

### t187ap46_L_6
- 說明：上市公司企業ESG資訊揭露彙總資料-董事會
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_6
- 欄位（10）：出表日期、報告年度、公司代號、公司名稱、董事席次(含獨立董事)(席)、獨立董事席次(席)、女性董事席次及比率-席、女性董事席次及比率-比率、董事出席董事會出席率、董監事進修時數符合進修要點比率

### t187ap46_L_7
- 說明：上市公司企業ESG資訊揭露彙總資料-投資人溝通
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_7
- 欄位（5）：出表日期、報告年度、公司代號、公司名稱、公司年度召開法說會次數(次)

### t187ap46_L_8
- 說明：上市公司企業ESG資訊揭露彙總資料-氣候相關議題管理
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_8
- 欄位（11）：出表日期、報告年度、公司代號、公司名稱、董事會與管理階層對於氣候相關風險與機會之監督及治理、辨識之氣候風險與機會如何影響企業之業務、策略及財務 (短期、中期、長期)、極端氣候事件及轉型行動對財務之影響、氣候風險之辨識、評估及管理流程如何整合於整體風險管理制度、若使用情境分析評估面對氣候變遷風險之韌性，應說明所使用之情境、參數、假設、分析因子及主要財務影響、若有因應管理氣候相關風險之轉型計畫，說明該計畫內容，及用於辨識及管理實體風險及轉型風險之指標與目標、使用內部碳定價作為規劃工具，應說明價格制定基礎,若有設定氣候相關目標，應說明所涵蓋之活動、溫室氣體排放範疇、規劃期程，每年達成進度等資訊；若使用碳抵換或再生能源憑證(RECs)以達成相關目標，應說明所抵換之減碳額度來源及數量或再生能源憑證(RECs)數量

### t187ap46_L_9
- 說明：上市公司企業ESG資訊揭露彙總資料-功能性委員會
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap46_L_9
- 欄位（9）：出表日期、報告年度、公司代號、公司名稱、薪酬委員會席次、薪酬委員會獨立董事席次、薪酬委員會出席率、審計委員會席次、審計委員會出席率

## 指數（5 個）

### FRMSA
- 說明：寶島股價指數歷史資料
- 網址：https://openapi.twse.com.tw/v1/indicesReport/FRMSA
- 欄位（3）：Date、FormosaIndex、FormosaTotalReturnIndex

### MFI94U
- 說明：發行量加權股價報酬指數
- 網址：https://openapi.twse.com.tw/v1/indicesReport/MFI94U
- 欄位（2）：Date、TAIEXTotalReturnIndex

### MI_5MINS_HIST
- 說明：發行量加權股價指數歷史資料
- 網址：https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
- 欄位（5）：Date、OpeningIndex、HighestIndex、LowestIndex、ClosingIndex

### MI_INDEX4
- 說明：每日上市上櫃跨市場成交資訊
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX4
- 欄位（4）：Date、TradeValue、FormosaIndex、Change

### TAI50I
- 說明：臺灣 50 指數歷史資料
- 網址：https://openapi.twse.com.tw/v1/indicesReport/TAI50I
- 欄位（3）：Date、Taiwan50Index、Taiwan50TotalReturnIndex

## 券商資料（9 個）

### ETFRank
- 說明：定期定額交易戶數統計排行月報表
- 網址：https://openapi.twse.com.tw/v1/ETFReport/ETFRank
- 欄位（7）：No、STOCKsSecurityCode、STOCKsName、STOCKsNumberofTradingAccounts、ETFsSecurityCode、ETFsName、ETFsNumberofTradingAccounts

### OpenData_BRK01
- 說明：證券商營業員男女人數統計資料
- 網址：https://openapi.twse.com.tw/v1/opendata/OpenData_BRK01
- 欄位（5）：出表日期、證券商代號、男性員工人數、女性員工人數、總人數

### OpenData_BRK02
- 說明：證券商分公司基本資料
- 網址：https://openapi.twse.com.tw/v1/opendata/OpenData_BRK02
- 欄位（6）：出表日期、證券商代號、證券商名稱、開業日、地址、電話

### brokerList
- 說明：證券商總公司基本資料
- 網址：https://openapi.twse.com.tw/v1/brokerService/brokerList
- 欄位（5）：Code、Name、EstablishmentDate、Address、Telephone

### secRegData
- 說明：開辦定期定額業務證券商名單
- 網址：https://openapi.twse.com.tw/v1/brokerService/secRegData
- 欄位（4）：SecuritiesFirmCode、Name、BrokerageBusinessStartingDate、WealthManagementBusinessStartingDate

### t187ap01
- 說明：券商業務別人員數
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap01
- 欄位（30）：出表日期、職位、受託買賣、受託買賣（衍生性商品銷售）、內部稽核、融資融券、證券借貸、自行買賣、其他人員、結算交割、股務人員、承銷人員、法令遵循、風險管理-模型管理、驗證人員-模型管理、內部稽核-模型管理、共同行銷、合作推廣、開戶、徵信、營業櫃檯輸單、主辦會計、財富管理、風險管理-其他、公司治理人員、受託管理私募股權基金人員、基金買賣及互易、數位服務（數位體驗專區）、數位服務（客戶服務中心）、合計

### t187ap18
- 說明：證券商基本資料
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap18
- 欄位（68）：出表日期、證券代號、券商(證券IB)簡稱、登記資本額（仟元）、實收資本額（仟元）、指撥營運金（仟元）、營利事業統一編號、變更日期、區域代碼、融資融券開辦日期、設立日期、開業日期、電話、傳真、交割金融機構、交割專戶帳號、違約專戶、錯帳專戶帳號、權證履約專戶帳號、代辦交割證券商(證券IB)代號、營業保證金保管銀行、發行狀況、業務種類、負責人、總經理、營業部經理、財務部經理、行政部門地址、營業處所－經、營業處所－經代表號、營業廳、營業處所－自、營業處所－自代表號、營業處所－承、營業處所－承代表號、股務代理商地址、備註、營業項目1、營業項目2、營業項目3、營業項目4、營業項目5、營業項目6、營業項目7、營業項目8、營業項目9、營業項目10、營業項目11、營業項目12、營業項目13、營業項目14、營業項目15、營業項目16、營業項目17、營業項目18、營業項目19、營業項目20、營業項目21、營業項目22、營業項目23、營業項目24、營業項目25、營業項目26、營業項目27、營業項目28、營業項目29、營業項目30、營業項目31

### t187ap20
- 說明：各券商每月月計表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap20
- 欄位（8）：出表日期、券商代號、券商名稱、科目、會計科目名稱、本月借方總額、本月貸方總額、借方餘額

### t187ap21
- 說明：各券商收支概況表資料
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap21
- 欄位（7）：出表日期、券商代號、券商名稱、科目、會計科目名稱、本月金額、累進金額

## 權證（3 個）

### t187ap36_L
- 說明：上市認購(售)權證年度發行量概況統計表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap36_L
- 欄位（8）：出表日期、發行人代號、發行人名稱、權證代號、名稱、標的代號、標的名稱、申請發行日期

### t187ap42_L
- 說明：上市認購(售)權證每日成交資料檔
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap42_L
- 欄位（6）：出表日期、交易日期、權證代號、權證名稱、成交金額、成交張數

### t187ap43_L
- 說明：上市認購(售)權證交易人數檔
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap43_L
- 欄位（3）：出表日期、日期、人數

## 其他（4 個）

### BFI61U
- 說明：中央登錄公債補息資料表
- 網址：https://openapi.twse.com.tw/v1/exchangeReport/BFI61U
- 欄位（6）：Code、Name、IssuedDate、StartingDate、CouponRate、DailyAccInterest

### eventList
- 說明：證交所活動訊息
- 網址：https://openapi.twse.com.tw/v1/news/eventList
- 欄位（3）：No、Title、Details

### newsList
- 說明：證交所新聞
- 網址：https://openapi.twse.com.tw/v1/news/newsList
- 欄位（3）：Title、Url、Date

### t187ap47_L
- 說明：基金基本資料彙總表
- 網址：https://openapi.twse.com.tw/v1/opendata/t187ap47_L
- 實測：實測可用（276 檔）
- 欄位（29）：出表日期、基金代號、基金簡稱、基金類型、基金中文名稱、基金英文名稱、標的指數/追蹤指數名稱、標的指數是否為客製化或需揭露相關資訊之指數、股票及債券投資比例說明、是否設有績效指標、績效指標中文名稱、績效指標英文名稱、是否包含國外成分股、基金統一編號、成立日期、上市日期、基金經理人、經理公司總機、經理公司地址、經理公司董事長、經理公司發言人、經理公司總經理、經理公司代理發言人、總代理人、發行單位數/轉換數、保管機構、保管機構電話、保管機構地址、備註


---

## 官方資料來源與 API 整理（2026-11-05 整合）

> 本節由使用者提供的 `MKLAB_台股官方資料來源_API整理.html` 轉為 Markdown 併入本檔，
> 內容涵蓋 MOPS／TWSE／TPEx 官方資料入口、端點清單與導入順序。
> **免責**：本清單為研究整理，非官方保證之永久 API；端點可能改版或限制存取，
> 正式使用前請逐一實測 HTTP 狀態、Content-Type、回應內容與涵蓋範圍（HTTP 200 不等於有效資料）。

整理可供 MKLAB Stock、GitHub Actions、Hermes Agent 或其他程式自動取得的台股官方資料入口，包含股票基本資料、財務報表、營收、股利、估值、交易、籌碼、ETF 與 ESG。
本文件彙整先前整理的官方資料端點與入口，並非官方保證的永久 API 清單。端點可能改版、移除、調整欄位或限制存取。正式納入 MKLAB 前，請逐一測試 HTTP 狀態、Content-Type、回應本文、欄位、資料期間及上市/上櫃涵蓋範圍。HTTP 200 不代表內容一定是有效資料。若端點無法使用，請以官方 Swagger/網站當期文件重新確認，不要直接假設 URL 正確或資料完整。
### 1. TWSE OpenAPI 基本資訊

官方 API 文件：[https://openapi.twse.com.tw/](https://openapi.twse.com.tw/)

常見 API 根路徑：`https://openapi.twse.com.tw/v1`。下表列出先前整理的端點，實際是否仍有效、欄位與資料期間均應以 Swagger 及實測為準。
### 2. 公司基本資料與公告

| 資料項目 | 端點 | 格式 | MKLAB 用途 |
|---|---|---|---|
| 上市公司基本資料 | [t187ap03_L](https://openapi.twse.com.tw/v1/opendata/t187ap03_L) | JSON | 公司代號、名稱、產業等基本主檔 |
| 公開發行公司基本資料 | [t187ap03_P](https://openapi.twse.com.tw/v1/opendata/t187ap03_P) | JSON | 擴充公司基本資料範圍 |
| 新上市公司 | [newlisting](https://openapi.twse.com.tw/v1/company/newlisting) | JSON | 追蹤新上市標的 |
| 終止上市資訊 | [suspendListingCsvAndHtml](https://openapi.twse.com.tw/v1/company/suspendListingCsvAndHtml) | 待確認 | 清理失效股票代號；確認實際回傳格式 |
| 上市公司重大訊息 | [t187ap04_L](https://openapi.twse.com.tw/v1/opendata/t187ap04_L) | JSON | 公司重大訊息追蹤 |
### 3. 月營收與財務報表

| 資料項目 | 端點 | 格式 | 用途 / 注意事項 |
|---|---|---|---|
| 上市公司每月營收 | [t187ap05_L](https://openapi.twse.com.tw/v1/opendata/t187ap05_L) | JSON | 計算 MoM、YoY、營收趨勢 |
| 綜合損益表－一般業 | [t187ap06_L_ci](https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci) | JSON | 營收、毛利、營業利益、稅後損益等 |
| 綜合損益表－金融業 | [t187ap06_L_basi](https://openapi.twse.com.tw/v1/opendata/t187ap06_L_basi) | JSON | 金融業專用格式 |
| 綜合損益表－金控業 | [t187ap06_L_fh](https://openapi.twse.com.tw/v1/opendata/t187ap06_L_fh) | JSON | 金控業專用格式 |
| 綜合損益表－保險業 | [t187ap06_L_ins](https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ins) | JSON | 保險業專用格式 |
| 綜合損益表－證券期貨業 | [t187ap06_L_bd](https://openapi.twse.com.tw/v1/opendata/t187ap06_L_bd) | JSON | 證券期貨業專用格式 |
| 資產負債表－一般業 | [t187ap07_L_ci](https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci) | JSON | 資產、負債、權益與 ROE 計算基礎 |
| 資產負債表－金融業 | [t187ap07_L_basi](https://openapi.twse.com.tw/v1/opendata/t187ap07_L_basi) | JSON | 金融業專用格式 |
| 資產負債表－金控業 | [t187ap07_L_fh](https://openapi.twse.com.tw/v1/opendata/t187ap07_L_fh) | JSON | 金控業專用格式 |
| 資產負債表－保險業 | [t187ap07_L_ins](https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ins) | JSON | 保險業專用格式 |
| 營益分析 | [t187ap17_L](https://openapi.twse.com.tw/v1/opendata/t187ap17_L) | JSON | 營業利益與獲利能力分析 |
| 各產業 EPS 統計 | [t187ap14_L](https://openapi.twse.com.tw/v1/opendata/t187ap14_L) | JSON | 產業獲利比較；確認資料期間 |
### 4. 股利、股東會與公司治理

| 資料項目 | 端點 | 格式 | MKLAB 用途 |
|---|---|---|---|
| 上市公司股利分派 | [t187ap45_L](https://openapi.twse.com.tw/v1/opendata/t187ap45_L) | JSON | 歷年現金/股票股利；需區分提議、決議與發放 |
| 股東會公告 | [t187ap38_L](https://openapi.twse.com.tw/v1/opendata/t187ap38_L) | JSON | 股東會公告追蹤 |
| 股東會日期及電子投票資訊 | [t187ap41_L](https://openapi.twse.com.tw/v1/opendata/t187ap41_L) | JSON | 股東會日期與投票資訊 |
| 董監事持股餘額 | [t187ap11_L](https://openapi.twse.com.tw/v1/opendata/t187ap11_L) | JSON | 董監事持股追蹤 |
| 大股東名單（10% 以上） | [t187ap02_L](https://openapi.twse.com.tw/v1/opendata/t187ap02_L) | JSON | 大股東持股分析 |
| 內部人持股轉讓申報 | [t187ap12_L](https://openapi.twse.com.tw/v1/opendata/t187ap12_L) | JSON | 內部人持股異動 |
| 內部人持股未轉讓 | [t187ap13_L](https://openapi.twse.com.tw/v1/opendata/t187ap13_L) | JSON | 申報後未完成轉讓資訊 |
| 董事長兼任總經理 | [t187ap33_L](https://openapi.twse.com.tw/v1/opendata/t187ap33_L) | JSON | 公司治理資訊 |
| 董監事酬金 | [t187ap29_A_L](https://openapi.twse.com.tw/v1/opendata/t187ap29_A_L) | JSON | 公司治理及酬金分析 |
### 5. 估值、股價交易與籌碼

| 資料項目 | 端點 | 格式 | MKLAB 用途 |
|---|---|---|---|
| 個股 PE、殖利率、PB | [BWIBBU_ALL](https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL) | JSON | 估值與殖利率篩選；ETF 是否包含須實測 |
| 每日 PE、殖利率、PB | [BWIBBU_d](https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d) | JSON | 歷史估值資料；確認日期參數/期間 |
| 上市個股日成交資訊 | [STOCK_DAY_ALL](https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL) | JSON | 每日收盤價、成交量等 |
| 日收盤價及月平均價 | [STOCK_DAY_AVG_ALL](https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL) | JSON | 價格趨勢與均線資料基礎 |
| 月成交資訊 | [FMSRFK_ALL](https://openapi.twse.com.tw/v1/exchangeReport/FMSRFK_ALL) | JSON | 月度成交統計 |
| 年成交資訊 | [FMNPTK_ALL](https://openapi.twse.com.tw/v1/exchangeReport/FMNPTK_ALL) | JSON | 年度成交統計 |
| 每日大盤統計 | [MI_INDEX](https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX) | JSON | 大盤指數與市場統計 |
| 融資融券餘額 | [MI_MARGN](https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN) | JSON | 信用交易與市場情緒 |
| 外資持股比例 | [MI_QFIIS_cat](https://openapi.twse.com.tw/v1/fund/MI_QFIIS_cat) | JSON | 外資持股分析 |
| 外資持股前 20 名 | [MI_QFIIS_sort_20](https://openapi.twse.com.tw/v1/fund/MI_QFIIS_sort_20) | JSON | 外資持股排行 |
| 除權息預告 | [TWT48U_ALL](https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL) | JSON | 除權息事件日曆 |
### 6. ETF、基金與權證

| 資料項目 | 端點 | 格式 | 用途 / 限制 |
|---|---|---|---|
| 基金基本資料彙總 | [t187ap47_L](https://openapi.twse.com.tw/v1/opendata/t187ap47_L) | JSON | ETF/基金基本資料；不等於每日持股明細 |
| ETF 定期定額排行 | [ETFRank](https://openapi.twse.com.tw/v1/ETFReport/ETFRank) | JSON | 定期定額熱門度參考 |
| 上市權證基本資料 | [t187ap37_L](https://openapi.twse.com.tw/v1/opendata/t187ap37_L) | JSON | 權證主檔 |
| 上市權證每日成交資料 | [t187ap42_L](https://openapi.twse.com.tw/v1/opendata/t187ap42_L) | JSON | 權證交易分析 |
| 上市權證交易人數 | [t187ap43_L](https://openapi.twse.com.tw/v1/opendata/t187ap43_L) | JSON | 權證交易人數統計 |

**ETF 成分股提醒：**ETF 基本資料、ETF 排行、ETF 每日持股明細是不同資料。若要取得 0050、006208、009816、00981A 等 ETF 的完整成分股，應另外查詢投信基金公司、指數公司及交易所官方揭露，並確認更新頻率與歷史檔案。
### 7. ESG / 永續資料

| 資料項目 | 端點 | 格式 |
|---|---|---|
| 溫室氣體排放 | [t187ap46_L_1](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_1) | JSON（待實測） |
| 能源管理 | [t187ap46_L_2](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_2) | JSON（待實測） |
| 水資源管理 | [t187ap46_L_3](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_3) | JSON（待實測） |
| 廢棄物管理 | [t187ap46_L_4](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_4) | JSON（待實測） |
| 人力發展 | [t187ap46_L_5](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_5) | JSON（待實測） |
| 董事會資訊 | [t187ap46_L_6](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_6) | JSON（待實測） |
| 投資人溝通 | [t187ap46_L_7](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_7) | JSON（待實測） |
### 8. MOPS 歷史月營收與財報下載

#### 歷史月營收 HTML 路徑範例

先前整理的歷史月營收路徑格式如下。以下為民國 115 年 9 月示例，請實際測試是否仍可存取及是否符合當期資料。

| 市場 | 示例網址 |
|---|---|
| 上市（sii） | [t21sc03_115_9_0.html](https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_115_9_0.html) |
| 上櫃（otc） | [t21sc03_115_9_0.html](https://mopsov.twse.com.tw/nas/t21/otc/t21sc03_115_9_0.html) |

路徑參數概念：`{市場別}` 可為 `sii`（上市）或 `otc`（上櫃）；`115` 為民國年；`9` 為月份；最後的類別代碼需依官方資料實測確認。這些範例為 HTML，不是 CSV。

#### XBRL / 財務報告

從 [MOPS 官網](https://mops.twse.com.tw/)進入財務報表與 XBRL 相關區域，查找財務報告、XBRL 分類標準及下載功能。可用於取得資產負債表、綜合損益表、現金流量表、權益變動表及會計師查核/核閱資訊。實際下載格式可能是 XBRL、HTML、PDF 或壓縮檔，應以當期下載介面為準。
### 9. 直接下載與自動化範例

#### 使用 curl 下載 JSON

```
curl -L "https://openapi.twse.com.tw/v1/opendata/t187ap05_L" -o monthly_revenue.json
```

#### 使用 JavaScript fetch

```
const url = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L";
const response = await fetch(url);
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const contentType = response.headers.get("content-type") || "";
if (!contentType.includes("json")) {
  throw new Error(`Unexpected Content-Type: ${contentType}`);
}
const data = await response.json();
if (!Array.isArray(data) || data.length === 0) {
  throw new Error("資料格式錯誤或資料為空");
}
console.log(`取得 ${data.length} 筆資料`);
```

#### GitHub Actions / Agent 驗證清單
- 記錄完整 URL、HTTP Method、查詢參數及抓取時間。
- 驗證 HTTP 狀態、Content-Type、回應本文與 JSON/CSV 結構。
- 檢查欄位名稱、資料筆數、日期、代號及重複資料。
- 區分缺值、數值 0、空字串、無資料及請求失敗。
- 確認上市與上櫃市場是否都有涵蓋，不能只用上市資料代表全市場。
- 保留原始回應與標準化資料，方便追查解析錯誤。
- 確認資料授權、使用條款、頻率限制及 GitHub Actions 執行限制。
- 失敗時重試並記錄錯誤，不可用空資料覆蓋最後一次有效資料。
### 10. MKLAB 建議導入順序
### 11. 官方入口與文件

#### MOPS 公開資訊觀測站

[mops.twse.com.tw](https://mops.twse.com.tw/)

#### TWSE OpenAPI

[openapi.twse.com.tw](https://openapi.twse.com.tw/)

#### TPEx OpenAPI

[tpex.org.tw/openapi](https://www.tpex.org.tw/openapi/)

#### TWSE 官方網站

[twse.com.tw](https://www.twse.com.tw/)
