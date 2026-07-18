/*
 * mklab-core.js — 全站唯一表格模組（配置驅動）
 * 零依賴、plain <script>（可 file:// 直接開，無 ES module CORS 問題）
 *
 * 設計：22 欄一次定義於 COLUMNS，每頁只選「要哪幾欄」+ 資料陣列。
 *       排序 / 格式化 / 分頁 / 箭頭 全部集中在此，避免多份拷貝漂移。
 *
 * 用法：
 *   const t = new DataTable('tblId', {
 *     cols: ['sym','price','chg','score','pe',...],   // 欄位 id 順序
 *     rows: [...],                                    // 資料陣列（物件）
 *     pageSize: 10,                                   // 0 = 不分頁
 *     fieldMap: { ind:'nm' },                         // 選用：欄位 id → 實際資料鍵
 *     ctx: { del:(sym)=>... },                        // 選用：給 'act' 類欄位用
 *     defaultSort: 'score',                           // 選用
 *   });
 *   t.setRows(newRows);  // 更新資料後重渲染
 */
(function (global) {
  'use strict';

  // ---------- 欄位註冊表（全站唯一來源）----------
  // type: num | pct | str | html | act
  //   num  : 數值排序，(v==null?-Infinity:v) 比較；格式化交給 fmt
  //   pct  : 同 num（漲跌%）
  //   str  : 字串排序（localeCompare）
  //   html : 不排序（sortable:false），原樣輸出
  //   act  : 動作欄（移除/選取），不排序
  const COLUMNS = {
    sym:   { label:'股票代號', type:'str', sortable:true,  fmt:r=>r.sym!=null?String(r.sym):'-' },
    name:  { label:'名稱',    type:'str', sortable:true,  fmt:r=>(r.name||r.nm||'-') },
    price: { label:'價格',    type:'num', sortable:true,  fmt:r=>r.price!=null?Number(r.price).toLocaleString():'-' },
    chg:   { label:'漲跌%',   type:'pct', sortable:true,  fmt:r=>cellPct(r.chg) },
    score: { label:'綜合評分',type:'num', sortable:true, defDir:-1, fmt:r=>r.score!=null?r.score:'-' },
    pe:    { label:'PE',      type:'num', sortable:true,  fmt:r=>r.pe!=null?Number(r.pe).toFixed(2):'-' },
    pb:    { label:'PB',      type:'num', sortable:true,  fmt:r=>r.pb!=null?Number(r.pb).toFixed(2):'-' },
    eps:   { label:'EPS',     type:'num', sortable:true,  fmt:r=>r.eps!=null?Number(r.eps).toFixed(2):'-' },
    roe:   { label:'ROE',     type:'num', sortable:true,  fmt:r=>(r.roe!=null?Number(r.roe).toFixed(2):'-') },
    roa:   { label:'ROA',     type:'num', sortable:true,  fmt:r=>(r.roa!=null?Number(r.roa).toFixed(2):'-') },
    trend: { label:'趨勢',    type:'str', sortable:true,  fmt:r=>(r.trend!=null?r.trend:(r.spct!=null?(r.spct>0?'+':'')+r.spct+'%':'-')) },
    spk:   { label:'趨勢',    type:'spark',sortable:false, fmt:r=>{ if(!r.spark||!r.spark.length) return '-'; const data=r.spark,min=Math.min(...data),max=Math.max(...data),rn=(max-min)||1; const p=data.map((d,i)=>`${(i/(data.length-1)*80).toFixed(1)},${(30-((d-min)/rn*30)).toFixed(1)}`).join(' '); const col=data[data.length-1]>=data[0]?'var(--up)':'var(--down)'; return `<div style="display:flex;justify-content:center"><svg viewBox="0 0 80 30" style="width:80px;height:30px;display:block"><polyline points="${p}" fill="none" stroke="${col}" stroke-width="1.5"/></svg></div>`; } },
    ind:   { label:'產業',    type:'str', sortable:true,  key:'ind', fmt:r=>(r.ind||r.nm||'-') },
    rsi:   { label:'RSI',     type:'num', sortable:true,  fmt:r=>r.rsi!=null?r.rsi:'-' },
    cap:   { label:'市值(億)',type:'num', sortable:true,  fmt:r=>{ const v = r.market_cap!=null ? r.market_cap/1e8 : (r.cap!=null?r.cap:null); return v!=null ? Number(v).toFixed(2) : '-'; } },
    w1:    { label:'1週',     type:'pct', sortable:true,  fmt:r=>cellPct(r.w1) },
    m1:    { label:'1月',     type:'pct', sortable:true,  fmt:r=>cellPct(r.m1) },
    m3:    { label:'3月',     type:'pct', sortable:true,  fmt:r=>cellPct(r.m3) },
    m6:    { label:'6月',     type:'pct', sortable:true,  fmt:r=>cellPct(r.m6) },
    ytd:   { label:'YTD',     type:'pct', sortable:true,  fmt:r=>cellPct(r.ytd) },
    y1:    { label:'1年',     type:'pct', sortable:true,  fmt:r=>cellPct(r.y1) },
    cnt:   { label:'檔數',    type:'num', sortable:true,  fmt:r=>r.cnt!=null?r.cnt:'-' },
    alert: { label:'提醒',    type:'html',sortable:false, fmt:r=>r.alert?`<span class="alert">${r.alert}</span>`:'—' },
    del:   { label:'移除',    type:'act', sortable:false, fmt:(r,ctx)=>`<span class="del" onclick="${ctx.__cb}('${r.sym}')">✕</span>` },
  };

  function cellPct(v){
    if(v==null) return '-';
    const n=Number(v);
    return (n>0?'+':'')+n.toFixed(2)+'%';
  }

  function getVal(col, row, fieldMap){
    const key = (fieldMap && fieldMap[col.id]) || col.key || col.id;
    return row[key];
  }

  function compare(a, b, col, fieldMap){
    let va = getVal(col, a, fieldMap);
    let vb = getVal(col, b, fieldMap);
    if(col.type === 'str'){
      return String(va||'').localeCompare(String(vb||''));
    }
    // num / pct
    va = (va==null) ? -Infinity : Number(va);
    vb = (vb==null) ? -Infinity : Number(vb);
    return va - vb;
  }

  function DataTable(tableId, opts){
    this.tableId = tableId;
    this.table = document.getElementById(tableId);
    if(!this.table) throw new Error('DataTable: #'+tableId+' 不存在');
    this.opts = opts || {};
    this.cols = (opts.cols||[]).map(id=>{
      const def = COLUMNS[id];
      if(!def) throw new Error('DataTable: 未知欄位 "'+id+'"');
      return Object.assign({ id:id }, def);
    });
    this.rows = opts.rows || [];
    this.fieldMap = opts.fieldMap || {};
    this.pageSize = opts.pageSize || 0;
    this.page = 1;
    this.sortKey = opts.defaultSort || (this.cols.find(c=>c.sortable)||{}).id || null;
    this.sortDir = (this.sortKey && COLUMNS[this.sortKey] && COLUMNS[this.sortKey].defDir) ? COLUMNS[this.sortKey].defDir : -1;
    // act 欄的回呼名（避免直接把函式塞進 onclick 字串，改掛全域）
    this._ctx = opts.ctx || {};
    if(opts.onDel){
      const name = '__dt_del_'+tableId;
      global[name] = opts.onDel;
      this._ctx.__cb = name;
    }
    this._build();
    this.render();
  }

  DataTable.prototype._build = function(){
    const thead = this.table.querySelector('thead');
    if(!thead) return;
    const tr = document.createElement('tr');
    this.cols.forEach(col=>{
      const th = document.createElement('th');
      th.textContent = col.label;
      th.setAttribute('data-k', col.id);
      if(col.sortable){ th.style.cursor = 'pointer'; }
      tr.appendChild(th);
    });
    thead.innerHTML = '';
    thead.appendChild(tr);
    if(!this.table.querySelector('tbody')){
      const tb = document.createElement('tbody');
      this.table.appendChild(tb);
    }
    // 注意：click 事件不再綁在 this.table 上（避免 DOM 引用漂移脫鉤）。
    // 改由 _register 註冊時建立「document 級事件委託」，按 tableId 找回實例（見下方 _register）。
  };

  DataTable.prototype.toggleSort = function(key){
    const col = this.cols.find(c=>c.id===key);
    if(!col || !col.sortable) return;
    if(this.sortKey === key){ this.sortDir *= -1; }
    else { this.sortKey = key; this.sortDir = (col.defDir!=null)?col.defDir:-1; }
    this.page = 1;
    try { console.log('[DT.toggleSort]', key, 'sortable=', col.sortable, 'dir=', this.sortDir, 'rows=', this.rows.length); } catch(e){}
    this.render();
  };

  DataTable.prototype.setRows = function(rows){
    this.rows = rows || [];
    this.page = 1;
    this.render();
  };

  DataTable.prototype._sorted = function(){
    if(!this.sortKey) return this.rows.slice();
    const col = this.cols.find(c=>c.id===this.sortKey);
    if(!col) return this.rows.slice();
    const self = this;
    try {
      return this.rows.slice().sort((a,b)=> compare(a,b,col,self.fieldMap) * self.sortDir);
    } catch(e){
      console.error('[DataTable._sorted]', this.sortKey, e);
      return this.rows.slice();
    }
  };

  DataTable.prototype.render = function(){
    const col = this.cols.find(c=>c.id===this.sortKey);
    // 表頭箭頭
    this.table.querySelectorAll('thead th').forEach(th=>{
      const k = th.getAttribute('data-k');
      let txt = th.textContent.replace(/\s*[▲▼]$/,'');
      if(k === this.sortKey && col && col.sortable){
        txt += (this.sortDir===-1 ? ' ▼' : ' ▲');
      }
      th.textContent = txt;
    });
    // 分頁
    let view = this._sorted();
    let totalPages = 1;
    if(this.pageSize > 0){
      totalPages = Math.max(1, Math.ceil(view.length / this.pageSize));
      if(this.page > totalPages) this.page = totalPages;
      view = view.slice((this.page-1)*this.pageSize, this.page*this.pageSize);
    }
    // 內容
    const ctx = this._ctx;
    const rowsHtml = view.map(r=>{
      const tds = this.cols.map(c=>{
        const rawVal = getVal(c,r,this.fieldMap);
        const v = (typeof c.fmt === 'function') ? c.fmt(r, ctx) : (rawVal!=null?rawVal:'-');
        let cls = (c.type==='pct') ? ((rawVal>=0)?'up':'down') : '';
        // 異常漲跌幅防禦：台股漲停限制 ±10%，槓桿ETF ±20%；超過視為資料異常標紅
        if(c.type==='pct' && typeof rawVal==='number' && Math.abs(rawVal) > 10){
          cls = 'warn';
        }
        return `<td class="${cls}">${v}</td>`;
      }).join('');
      return `<tr>${tds}</tr>`;
    }).join('') || `<tr><td colspan="${this.cols.length}" style="text-align:center;color:var(--muted)">無資料</td></tr>`;
    this.table.querySelector('tbody').innerHTML = rowsHtml;
    // 分頁條
    const pagerId = this.opts.pagerId;
    if(pagerId && this.pageSize>0){
      const el = document.getElementById(pagerId);
      if(el){
        let b='';
        for(let i=1;i<=totalPages;i++) b+=`<button class="${i===this.page?'on':''}" onclick="__dt_goto('${this.opts._inst}',${i})">${i}</button>`;
        el.innerHTML=b;
      }
    }
  };

  // 分頁跳轉（掛全域）+ 按 tableId 查表（document 級 click 委託用）
  const _instances = {};   // keyed by opts._inst（分頁）
  const _byTable = {};     // keyed by tableId（click 委託）
  let _seq = 0;
  let _docBound = false;
  DataTable.prototype._register = function(){
    this.opts._inst = 'dt'+(_seq++);
    _instances[this.opts._inst] = this;
    _byTable[this.tableId] = this;
    global.__dt_goto = function(inst, p){ const t=_instances[inst]; if(t){ t.page=p; t.render(); } };
    // 全站只綁一次：document 層監聽 thead th 點擊 → 按 tableId 找回實例排序。
    // 優點：永遠不依賴「建構時捕獲的 DOM 引用」，徹底消除脫鉤類錯誤。
    if(!_docBound){
      document.addEventListener('click', function(e){
        const th = e.target.closest('thead th');
        if(!th) return;
        const tbl = th.closest('table');
        if(!tbl || !tbl.id) return;
        const inst = _byTable[tbl.id];
        if(inst){ console.log('[DT doc-click]', tbl.id, th.getAttribute('data-k')); inst.toggleSort(th.getAttribute('data-k')); }
      });
      _docBound = true;
      console.log('[DT] document-level click delegation bound');
    }
  };

  // 包裝建構：自動註冊實例供分頁用
  const _origNew = DataTable;
  function create(tableId, opts){
    const t = new _origNew(tableId, opts);
    t._register();
    return t;
  }

  global.MKLAB = { 
  COLUMNS, 
  DataTable: create, 
  cellPct,
  Drawer: Drawer,
  Shell: Shell,
  Watch: Watch,
  initDrawer: function() { Drawer.init(); },
  setLang: function(l) { Drawer.setLang(l); }
};

  // ============================================================
  // 共用設定抽屜（全站唯一，所有頁一致）
  // ============================================================
  const DRAWER_CFG = {
    appearance: {
      dark: true,                                   // 顯示深色主題開關
      darkOn: true,                                 // 預設開
      lang: true,                                   // 顯示語言切換
    },
    help: {
      doc: 'mklab-stock-help.html',                  // 功能說明（使用/資料源/評分標準）
      log: 'mklab-stock-log.html',                    // 開發日誌
      readme: 'https://github.com/evanhsia-git/mklab-stock#readme', // GitHub README
    },
    system: {
      version: 'dashboard v3.0',
      source:  'TWSE/TPEX/Yahoo/Stooq',
      updated: '2026-07-13',
      status:  '● 正常運作',
    },
  };

  function drawerHTML(){
    const c = DRAWER_CFG;
    const darkOn = (localStorage.getItem('mk_dark')!=='0') && c.appearance.darkOn;
    const lang = localStorage.getItem('mk_lang') || 'zh';
    let h = '<h3>設定</h3>';
    h += '<h4>外觀</h4>';
    if(c.appearance.dark){
      h += `<div class="row"><span>深色主題</span><button class="switch ${darkOn?'on':''}" id="swDark" onclick="MKLAB.Drawer.toggleDark()"></button></div>`;
    }
    if(c.appearance.lang){
      h += `<div class="row"><span>語言</span><div class="seg"><button id="langZh" class="${lang==='zh'?'on':''}" onclick="MKLAB.setLang('zh')">中文</button><button id="langEn" class="${lang==='en'?'on':''}" onclick="MKLAB.setLang('en')">EN</button></div></div>`;
    }
    h += '<h4>說明</h4>';
    h += `<div class="row"><a href="${c.help.doc}">功能說明（使用/資料源/評分標準）↗</a></div>`;
    h += `<div class="row"><a href="${c.help.log}">開發日誌 ↗</a></div>`;
    h += `<div class="row"><a href="${c.help.readme}" target="_blank" rel="noopener">GitHub README ↗</a></div>`;
    h += '<h4>System</h4>';
    const s = c.system;
    h += `<div class="sys-note">版本：${s.version}<br>資料源：${s.source}<br>最後更新：${s.updated}<br>狀態：<span class="up">${s.status}</span></div>`;
    return h;
  }

  const Drawer = {
    init(){
      const el = document.getElementById('drawer');
      if(!el) return;
      // 保留現有的 close-x 和 drawer-content，只注入 drawerHTML()
      const content = el.querySelector('.drawer-content');
      if(content){
        content.innerHTML = drawerHTML();
      }
      // 套用初始深淺色
      const darkOn = (localStorage.getItem('mk_dark')!=='0') && DRAWER_CFG.appearance.darkOn;
      document.documentElement.setAttribute('data-theme', darkOn?'dark':'light');
      const sw = document.getElementById('swDark'); if(sw) sw.classList.toggle('on', darkOn);
      // 動態更新「最後更新」日期：讀 stocks.json 的 meta.as_of
      fetch('data/stocks.json').then(r=>r.ok?r.json():null).then(d=>{
        const asof = d && d.meta && d.meta.as_of;
        if(asof){
          DRAWER_CFG.system.updated = asof;
          const note = el.querySelector('.sys-note');
          if(note) note.innerHTML = `版本：${DRAWER_CFG.system.version}<br>資料源：${DRAWER_CFG.system.source}<br>最後更新：${asof}<br>狀態：<span class="up">${DRAWER_CFG.system.status}</span>`;
        }
      }).catch(e=>{ console.warn('[Drawer] fetch stocks.json failed:', e); });
    },
    open(){
      const el = document.getElementById('drawer'); if(!el) return;
      el.classList.add('open');
      const mask = document.querySelector('.drawer-mask'); if(mask) mask.classList.add('open');
      // index 首頁有自選，開抽屜時刷新
      if(typeof renderWatch === 'function') renderWatch();
      // 刷新 System 區塊的「最後更新」日期
      fetch('data/stocks.json').then(r=>r.ok?r.json():null).then(d=>{
        const asof = d && d.meta && d.meta.as_of;
        if(asof){
          DRAWER_CFG.system.updated = asof;
          const note = el.querySelector('.sys-note');
          if(note){
            const sys = DRAWER_CFG.system;
            note.innerHTML = `版本：${sys.version}<br>資料源：${sys.source}<br>最後更新：${asof}<br>狀態：<span class="up">${sys.status}</span>`;
          }
        }
      }).catch(e=>{ console.warn('[Drawer.open] fetch stocks.json failed:', e); });
      // 啟動系統時間定時器
      this.startSysTimer();
    },
    close(){
      const el = document.getElementById('drawer'); if(!el) return;
      el.classList.remove('open');
      const mask = document.querySelector('.drawer-mask'); if(mask) mask.classList.remove('open');
      // 停止系統時間定時器
      this.stopSysTimer();
    },
    toggleDark(){
      const on = document.documentElement.getAttribute('data-theme')==='dark';
      const next = !on;
      document.documentElement.setAttribute('data-theme', next?'dark':'light');
      localStorage.setItem('mk_dark', next?'1':'0');
      const sw = document.getElementById('swDark'); if(sw) sw.classList.toggle('on', next);
    },
    setLang(l){
      localStorage.setItem('mk_lang', l);
      const zh = document.getElementById('langZh'), en = document.getElementById('langEn');
      if(zh) zh.classList.toggle('on', l==='zh');
      if(en) en.classList.toggle('on', l==='en');
    },
    // 系統時間定時器：每分鐘更新一次 System 區塊的日期/時間/星期
    startSysTimer(){
          if (this._sysTimer) return;
          this._sysTimer = setInterval(() => {
            const el = document.getElementById('drawer');
            if (!el || !el.classList.contains('open')) return;
            const note = el.querySelector('.sys-note');
            if (!note) return;
            const now = new Date();
            const sys = DRAWER_CFG.system;
            const dateStr = now.toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' });
            const timeStr = now.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
            const weekStr = ['日','一','二','三','四','五','六'][now.getDay()];
            note.innerHTML = `版本：${sys.version}<br>資料源：${sys.source}<br>最後更新：${sys.updated}<br>當前時間：${dateStr} (週${weekStr}) ${timeStr}<br>狀態：<span class="up">${sys.status}</span>`;
          }, 60000); // 每分鐘
          // 立即執行一次
          try {
            const el = document.getElementById('drawer');
            if (el && el.classList.contains('open')) {
              const note = el.querySelector('.sys-note');
              if (note) {
                const now = new Date();
                const sys = DRAWER_CFG.system;
                const dateStr = now.toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' });
                const timeStr = now.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
                const weekStr = ['日','一','二','三','四','五','六'][now.getDay()];
                note.innerHTML = `版本：${sys.version}<br>資料源：${sys.source}<br>最後更新：${sys.updated}<br>當前時間：${dateStr} (週${weekStr}) ${timeStr}<br>狀態：<span class="up">${sys.status}</span>`;
              }
            }
          } catch(e) {
            console.warn('[Drawer.startSysTimer] initial update failed:', e);
          }
        },
    stopSysTimer(){
      if (this._sysTimer) {
        clearInterval(this._sysTimer);
        this._sysTimer = null;
      }
    },
  };

  // ============================================================
  // 共用自選清單（watchlist 與首頁「我的自選」共用同一份）
  //   localStorage 'mk_watch' = JSON 陣列 [{sym,name}]
  //   價格/漲跌優先從 stocks.json 取真實值（caller 傳入 map）
  // ============================================================
  const WATCH_KEY = 'mk_watch';
  const DEFAULT_WATCH = ['2330','2454','2308','2317','3711'];

  const Watch = {
    list(){
      try {
        const v = JSON.parse(localStorage.getItem(WATCH_KEY));
        if(Array.isArray(v) && v.length) return v;
      } catch(e){}
      return DEFAULT_WATCH.map(s=>({sym:s, name:''}));
    },
    save(arr){ localStorage.setItem(WATCH_KEY, JSON.stringify(arr)); },
    add(sym, name){
      const arr = this.list();
      if(arr.some(x=>x.sym===sym)) return arr;
      arr.push({sym, name:name||''});
      this.save(arr); return arr;
    },
    remove(sym){
      const arr = this.list().filter(x=>x.sym!==sym);
      this.save(arr); return arr;
    },
    // 用 stocks.json map（{sym:{price,chg,pe,roe,alert,name}}）補真實值
    decorate(priceMap){
      return this.list().map(x=>{
        const p = priceMap && priceMap[x.sym];
        return Object.assign({}, x, {
          name:  p&&p.name ? p.name : x.name,   // 優先用 stocks.json 真實名稱
          price: p&&p.price!=null?p.price:null,
          chg:   p&&p.chg!=null?p.chg:null,
          pe:    p&&p.pe!=null?p.pe:null,
          pb:    p&&p.pb!=null?p.pb:null,
          roe:   p&&p.roe!=null?p.roe:null,
          alert: p&&p.alert?p.alert:'',
        });
      });
    },
  };

  // ============================================================
  // 頂部工具列模組（搜尋鍵 / 深色按鈕 / GitHub 跳轉 / 設定鍵）
  //   5 頁共用同一份標記與行為，避免各頁重複寫導覽與工具列。
  //   呼叫：MKLAB.Shell.mount({ active:'market', onSearch:fn })
  // ============================================================
  const NAV = [
    { key:'market',    label:'Market',    href:'index.html' },
    { key:'screener',  label:'Screener',  href:'mklab-stock-screener.html' },
    { key:'research',  label:'Research',  href:'mklab-stock-research.html' },
    { key:'industry',  label:'Industry',  href:'mklab-stock-industry.html' },
    { key:'watchlist', label:'Watchlist', href:'mklab-stock-watchlist.html' },
  ];
  const SHELL_CFG = {
    brand: 'mklab-stock',
    github: 'https://github.com/evanhsia-git/mklab-stock',
  };
  const ICON = {
    search:'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    dark:'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    github:'<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.9a3.4 3.4 0 0 0-1-2.6c3-.3 6-1.5 6-6.5a5 5 0 0 0-1.4-3.5a4.7 4.7 0 0 0-.1-3.5s-1.1-.3-3.5 1.3a12 12 0 0 0-6.3 0C6.5 1.3 5.4 1.6 5.4 1.6a4.7 4.7 0 0 0-.1 3.5A5 5 0 0 0 4 8.6c0 5 3 6.2 6 6.5a3.4 3.4 0 0 0-1 2.6V22"/></svg>',
    gear:'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',
  };

  const Shell = {
    mount(opts){
      opts = opts || {};
      const bar = document.getElementById('utilbar');
      if(!bar) return;
      const active = opts.active || '';
      const navHtml = NAV.map(n=>`<a href="${n.href}" class="${n.key===active?'active':''}">${n.label}</a>`).join('');
      // 靜態殼由 HTML 提供（<div id="utilbar" class="utilbar"><nav id="mainNav" class="nav"></nav>...），
      // 此處只填充導覽連結與右側工具鈕，保留 <nav> 與 .utilbar 在靜態 DOM（QA 靜態掃描可見）。
      const nav = document.getElementById('mainNav');
      if(nav) nav.innerHTML = navHtml;
      // 品牌（靜態殼的 #brand，保持 SHELL_CFG.brand 單一來源）
      const brand = document.getElementById('brand');
      if(brand) brand.textContent = SHELL_CFG.brand;
      // 右側工具區：搜尋 / 深色 / GitHub / 設定
      bar.querySelectorAll('[data-shell-tools]').forEach(el=>el.remove()); // 避免重複掛載
      const tools = document.createElement('span');
      tools.setAttribute('data-shell-tools','');
      tools.className = 'shell-tools';
      tools.style.cssText = 'display:flex; align-items:center; gap:8px;';
      tools.innerHTML =
        `<div class="search collapsed" id="searchBox">` +
          `<input id="q" placeholder="搜尋代號，如 2330" onkeydown="if(event.key==='Enter')MKLAB.Shell.doSearch()">` +
          `<button class="fab-btn" style="width:32px;height:32px" onclick="MKLAB.Shell.toggleSearch()" title="搜尋">${ICON.search}</button>` +
        `</div>` +
        `<button class="fab-btn" onclick="MKLAB.Drawer.toggleDark()" title="主題">${ICON.dark}</button>` +
        `<a class="fab-btn" href="${SHELL_CFG.github}" target="_blank" rel="noopener" title="GitHub">${ICON.github}</a>` +
        `<button class="fab-btn" onclick="MKLAB.Drawer.open()" title="設定">${ICON.gear}</button>`;
      bar.appendChild(tools);
      // 深色按鈕同步初始狀態
      const darkOn = (localStorage.getItem('mk_dark')!=='0') && DRAWER_CFG.appearance.darkOn;
      document.documentElement.setAttribute('data-theme', darkOn?'dark':'light');
    },
    toggleSearch(){
      const b = document.getElementById('searchBox');
      if(!b) return;
      const inp = b.querySelector('input');
      const exp = b.classList.toggle('expanded');
      b.classList.toggle('collapsed', !exp);
      if(exp){ inp.style.display='block'; inp.focus(); } else { inp.style.display='none'; }
    },
    doSearch(){
      const v = document.getElementById('q');
      const val = v ? v.value.trim() : '';
      if(!val) return;
      window.location.href = 'mklab-stock-research.html?sym=' + encodeURIComponent(val);
    },
  };

  global.MKLAB.DataTable = create;
  global.MKLAB.drawerHTML = drawerHTML;
  global.MKLAB.Drawer = Drawer;
  global.MKLAB.Watch = Watch;
  global.MKLAB.Shell = Shell;
  global.MKLAB.DRAWER_CFG = DRAWER_CFG;
  global.MKLAB.initDrawer = function(){ Drawer.init(); };

})(window);