#!/usr/bin/env python3
"""
mklab-stock 資料驗證腳本（Data Validation）

用途：
  - 檢查 stocks.json 關鍵欄位合法性
  - 檢查數值合理性（PE/PB/ROE/EPS/Market Cap/Close 等）
  - 檢查資料新鮮度
  - 檢查必填欄位完整性
  - 產出驗證報告供 QA Gate 使用

用法：
  python scripts/validate_data.py [--json output.json]

退出碼：0=全部通過, 1=有 ERROR, 2=有 WARNING（可配置）
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
STOCKS_PATH = os.path.join(OUT, "stocks.json")


class DataValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.stats = {
            "total": 0,
            "checked": 0,
            "fields_checked": 0,
            "errors": 0,
            "warnings": 0,
        }

    def log_error(self, msg: str, stock_id: str = "", field: str = ""):
        self.errors.append({"stock_id": stock_id, "field": field, "message": msg})
        self.stats["errors"] += 1

    def log_warning(self, msg: str, stock_id: str = "", field: str = ""):
        self.warnings.append({"stock_id": stock_id, "field": field, "message": msg})
        self.stats["warnings"] += 1

    def check_required_fields(self, stock: Dict) -> bool:
        """檢查必填欄位：sym, name 為必填；price 可為 None（停牌/無成交）"""
        required = ["sym", "name"]
        missing = [f for f in required if stock.get(f) is None]
        if missing:
            self.log_error(f"缺少必填欄位: {missing}", stock.get("sym", ""), ", ".join(missing))
            return False
        # price 為 None 視為停牌/無成交，記警告但不阻擋
        if stock.get("price") is None:
            self.log_warning("price 為 None（停牌/無成交）", stock.get("sym", ""), "price")
        return True

    def check_numeric_ranges(self, stock: Dict):
        """檢查數值合理性"""
        sym = stock.get("sym", "")

        # PE: 合理範圍 -50 到 500
        pe = stock.get("pe")
        if pe is not None and not (-50 <= pe <= 500):
            self.log_warning(f"PE 值異常: {pe}", sym, "pe")

        # PB: 合理範圍 -10 到 100
        pb = stock.get("pb")
        if pb is not None and not (-10 <= pb <= 100):
            self.log_warning(f"PB 值異常: {pb}", sym, "pb")

        # ROE: 合理範圍 -200% 到 200%
        roe = stock.get("roe")
        if roe is not None and not (-200 <= roe <= 200):
            self.log_warning(f"ROE 值異常: {roe}", sym, "roe")

        # ROA: 合理範圍 -100% 到 100%
        roa = stock.get("roa")
        if roa is not None and not (-100 <= roa <= 100):
            self.log_warning(f"ROA 值異常: {roa}", sym, "roa")

        # EPS: 合理範圍 -1000 到 1000
        eps = stock.get("eps")
        if eps is not None and not (-1000 <= eps <= 1000):
            self.log_warning(f"EPS 值異常: {eps}", sym, "eps")

        # Market Cap: 必須 > 0
        mc = stock.get("market_cap")
        if mc is not None and mc <= 0:
            self.log_warning(f"Market Cap 異常 (<=0): {mc}", sym, "market_cap")

        # Price: 必須 > 0
        price = stock.get("price")
        if price is not None and price <= 0:
            self.log_error(f"Price 異常 (<=0): {price}", sym, "price")

        # Volume: 必須 >= 0
        vol = stock.get("volume")
        if vol is not None and vol < 0:
            self.log_warning(f"Volume 異常 (<0): {vol}", sym, "volume")

        # Chg: 合理範圍 -30% 到 30%（單日漲跌幅限制）
        chg = stock.get("chg")
        if chg is not None and not (-30 <= chg <= 30):
            self.log_warning(f"漲跌幅異常: {chg}%", sym, "chg")

    def check_data_freshness(self, stock: Dict):
        """檢查資料新鮮度"""
        sym = stock.get("sym", "")
        last_updated = stock.get("last_updated")
        if last_updated:
            try:
                update_date = datetime.strptime(last_updated, "%Y-%m-%d")
                if datetime.now() - update_date > timedelta(days=7):
                    self.log_warning(f"資料超過 7 天未更新: {last_updated}", sym, "last_updated")
            except ValueError:
                self.log_warning(f"last_updated 格式錯誤: {last_updated}", sym, "last_updated")

    def check_source_quality(self, stock: Dict):
        """檢查資料來源品質標記"""
        sym = stock.get("sym", "")
        source = stock.get("source")
        quality = stock.get("quality")

        if source not in ["TWSE", "TPEX", "Yahoo Finance"]:
            self.log_warning(f"未知資料來源: {source}", sym, "source")

        if quality not in ["official", "yfinance_fallback"]:
            self.log_warning(f"未知品質等級: {quality}", sym, "quality")

    def check_etf_flags(self, stock: Dict):
        """檢查 ETF 標記一致性"""
        sym = stock.get("sym", "")
        is_etf = stock.get("is_etf", False)
        name = stock.get("name", "")

        etf_keywords = ["ETF", "基金", "指數", "正", "反", "槓桿", "反向", "期貨", "配息", "高息", "優息", "收益"]
        looks_like_etf = any(kw in name for kw in etf_keywords)

        if is_etf != looks_like_etf:
            self.log_warning(f"ETF 標記可能不一致: is_etf={is_etf}, name={name}", sym, "is_etf")

    def validate(self) -> Dict:
        """執行完整驗證"""
        if not os.path.exists(STOCKS_PATH):
            self.log_error(f"找不到 stocks.json: {STOCKS_PATH}")
            return self.report()

        with open(STOCKS_PATH, encoding="utf-8") as f:
            data = json.load(f)

        meta = data.get("meta", {})
        stocks = data.get("stocks", [])

        self.stats["total"] = len(stocks)

        for stock in stocks:
            self.stats["checked"] += 1

            if not self.check_required_fields(stock):
                continue

            self.check_numeric_ranges(stock)
            self.check_data_freshness(stock)
            self.check_source_quality(stock)
            self.check_etf_flags(stock)

        return self.report()

    def report(self) -> Dict:
        return {
            "success": len(self.errors) == 0,
            "stats": self.stats,
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(description="mklab-stock 資料驗證")
    parser.add_argument("--json", help="輸出 JSON 報告路徑")
    parser.add_argument("--fail-on-warning", action="store_true", help="WARNING 也視為失敗")
    args = parser.parse_args()

    validator = DataValidator()
    result = validator.validate()

    # 輸出報告
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    # 終端機輸出摘要
    print(f"\n=== mklab-stock Data Validation ===")
    print(f"時間: {result['timestamp']}")
    print(f"總筆數: {result['stats']['total']}")
    print(f"檢查筆數: {result['stats']['checked']}")
    print(f"Errors: {result['stats']['errors']}")
    print(f"Warnings: {result['stats']['warnings']}")

    if result["errors"]:
        print(f"\n❌ Errors ({len(result['errors'])}):")
        for e in result["errors"][:10]:
            print(f"  - [{e['stock_id']}] {e['field']}: {e['message']}")
        if len(result["errors"]) > 10:
            print(f"  ... 共 {len(result['errors'])} 筆")

    if result["warnings"]:
        print(f"\n⚠️ Warnings ({len(result['warnings'])}):")
        for w in result["warnings"][:10]:
            print(f"  - [{w['stock_id']}] {w['field']}: {w['message']}")
        if len(result["warnings"]) > 10:
            print(f"  ... 共 {len(result['warnings'])} 筆")

    if result["success"]:
        print(f"\n✅ 驗證通過")
        sys.exit(0)
    else:
        print(f"\n❌ 驗證失敗: {len(result['errors'])} errors")
        sys.exit(1)


if __name__ == "__main__":
    main()