from flask import Flask, jsonify, request, render_template_string
import yfinance as yf
import sqlite3
import os

app = Flask(__name__)

# -------------------------------------------------------------
# CLOUD DATABASE CONTEXT CONFIGURATION
# -------------------------------------------------------------
# This guarantees that the SQLite database file initializes cleanly 
# in the exact absolute directory path where the server lives in the cloud.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "trading_simulator.db")

def init_db():
    """Creates a local SQLite database file to permanently store positions."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT NOT NULL,
            type TEXT NOT NULL,
            entry_price REAL NOT NULL,
            volume REAL NOT NULL,
            allocated_margin REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Custom target alerts threshold settings
target_alerts = {
    "Gold (XAU/USD)": {"high": 4500.0, "low": 4000.0},
    "Silver (XAG/USD)": {"high": 75.0, "low": 55.0},
    "Brent Crude Oil": {"high": 95.0, "low": 75.0}
}

def get_market_data():
    """Fetches real-time prices AND calculates a 30-day Simple Moving Average (SMA) trend."""
    tickers = {
        "Gold (XAU/USD)": "GC=F",
        "Silver (XAG/USD)": "SI=F",
        "Brent Crude Oil": "BZ=F"
    }
    data = {}
    for name, sym in tickers.items():
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="30d")
            if not df.empty:
                current_price = float(df['Close'].iloc[-1])
                sma_30 = float(df['Close'].mean())
                
                trend = "🟢 BULLISH" if current_price >= sma_30 else "🔴 BEARISH"
                
                data[name] = {
                    "price": current_price,
                    "trend": trend,
                    "sma": round(sma_30, 2)
                }
        except Exception:
            pass
    return data

# -------------------------------------------------------------
# FRONT-END USER INTERFACE (HTML/CSS + LIVE AUTO-REFRESH JAVASCRIPT)
# -------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Ultimate Pro Trading Station</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0c0c0e; color: #e0e0e6; margin: 0; padding: 40px; }
        .container { max-width: 1100px; margin: 0 auto; }
        h1, h2 { color: #ffffff; border-bottom: 2px solid #222227; padding-bottom: 10px; margin-top: 0; }
        .grid { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 20px; margin-bottom: 30px; }
        .card { background-color: #141419; border-radius: 8px; padding: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.4); border: 1px solid #1f1f24; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #8a8a93; font-size: 14px; }
        input, select { width: 100%; padding: 12px; border-radius: 4px; border: 1px solid #2a2a32; background-color: #1c1c24; color: #fff; box-sizing: border-box; }
        button { background-color: #2f69ff; color: white; border: none; padding: 12px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold; transition: background 0.2s; }
        button:hover { background-color: #4b7fff; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #1f1f24; }
        th { background-color: #191921; color: #8a8a93; font-size: 13px; text-transform: uppercase; }
        .profit { color: #00e676; font-weight: bold; }
        .loss { color: #ff1744; font-weight: bold; }
        .alert-box { background-color: #ff9100; color: #0c0c0e; padding: 12px; border-radius: 4px; margin-bottom: 15px; font-weight: bold; }
        .trend-badge { font-size: 12px; padding: 3px 6px; border-radius: 4px; background-color: #1c1c24; margin-left: 8px; }
    </style>
    
    <script>
        async function refreshDashboardData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                for (const [asset, info] of Object.entries(data.market_prices)) {
                    const priceElem = document.getElementById(`price-${asset}`);
                    const trendElem = document.getElementById(`trend-${asset}`);
                    if (priceElem) priceElem.innerText = `$${info.price.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
                    if (trendElem) trendElem.innerText = `${info.trend} (30d SMA: $${info.sma})`;
                }
                
                const pnlElem = document.getElementById('total-portfolio-pnl');
                pnlElem.innerText = `$${data.total_portfolio_pnl.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
                pnlElem.className = data.total_portfolio_pnl >= 0 ? 'profit' : 'loss';
                
                data.active_simulations.forEach(trade => {
                    const pnlTd = document.getElementById(`pnl-${trade.trade_id}`);
                    const currentTd = document.getElementById(`current-${trade.trade_id}`);
                    const marginTd = document.getElementById(`margin-${trade.trade_id}`);
                    const statusSpan = document.getElementById(`status-${trade.trade_id}`);
                    
                    if (currentTd) currentTd.innerText = `$${trade.current_price.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
                    if (pnlTd) {
                        pnlTd.innerText = `$${trade.floating_pnl.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
                        pnlTd.className = trade.floating_pnl >= 0 ? 'profit' : 'loss';
                    }
                    if (marginTd) marginTd.innerText = `${trade.margin_level_percent}%`;
                    if (statusSpan) {
                        statusSpan.innerText = trade.status;
                        statusSpan.style.backgroundColor = trade.status === 'HEALTHY' ? '#00e676' : '#ff1744';
                    }
                });
                
                const alertContainer = document.getElementById('alerts-container');
                alertContainer.innerHTML = '';
                data.alerts_triggered.forEach(alert => {
                    alertContainer.innerHTML += `<div class="alert-box">${alert}</div>`;
                });
                
            } catch (err) {
                console.error("Background data refresh failed", err);
            }
        }
        setInterval(refreshDashboardData, 3000);
    </script>
</head>
<body>
    <div class="container">
        <h1>🦅 Ultimate Portfolio Terminal</h1>
        
        <div id="alerts-container"></div>

        <div class="grid">
            <div class="card">
                <h2>📈 Real-Time Asset Trends</h2>
                <table>
                    <tr><th>Asset</th><th>Live Price</th><th>30-Day SMA Trend Direction</th></tr>
                    {% for asset, info in market_prices.items() %}
                        <tr>
                            <td><strong>{{ asset }}</strong></td>
                            <td id="price-{{ asset }}">${{ "{:,.2f}".format(info.price) }}</td>
                            <td><span id="trend-{{ asset }}" class="trend-badge">{{ info.trend }} (30d SMA: ${{ info.sma }})</span></td>
                        </tr>
                    {% endfor %}
                </table>
                <h3 style="margin-top: 25px;">💵 Net Floating PnL: 
                    <span id="total-portfolio-pnl" class="{% if total_pnl >= 0 %}profit{% else %}loss{% endif %}">
                        ${{ "{:,.2f}".format(total_pnl) }}
                    </span>
                </h3>
            </div>

            <div class="card">
                <h2>📥 Permanent Trade Input</h2>
                <form action="/add_trade" method="POST">
                    <div class="form-group">
                        <label>Select Market Asset</label>
                        <select name="asset">
                            <option value="Gold (XAU/USD)">Gold (XAU/USD)</option>
                            <option value="Silver (XAG/USD)">Silver (XAG/USD)</option>
                            <option value="Brent Crude Oil">Brent Crude Oil</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Position Direction</label>
                        <select name="type">
                            <option value="BUY">BUY (Long)</option>
                            <option value="SELL">SELL (Short)</option>
                        </select>
                    </div>
                    <div class="grid" style="margin-bottom:0; gap:10px;">
                        <div class="form-group">
                            <label>Entry Execution Price ($)</label>
                            <input type="number" step="0.01" name="entry_price" placeholder="e.g. 2310" required>
                        </div>
                        <div class="form-group">
                            <label>Trade Size Volume</label>
                            <input type="number" step="0.1" name="volume" placeholder="e.g. 15" required>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Allocated Collateral Margin ($)</label>
                        <input type="number" step="0.01" name="allocated_margin" placeholder="e.g. 1500" required>
                    </div>
                    <button type="submit">Commit Position to DB</button>
                </form>
            </div>
        </div>

        <div class="card">
            <h2>💼 Live Portfolio Core Engines</h2>
            <table>
                <thead>
                    <tr><th>ID</th><th>Asset</th><th>Type</th><th>Entry Price</th><th>Live Price</th><th>Volume</th><th>Floating PnL</th><th>Margin Level</th><th>Risk Status</th></tr>
                </thead>
                <tbody>
                    {% for t in active_trades %}
                        <tr>
                            <td>#{{ t.trade_id }}</td>
                            <td>{{ t.asset }}</td>
                            <td><strong>{{ t.direction }}</strong></td>
                            <td>${{ "{:,.2f}".format(t.entry_price) }}</td>
                            <td id="current-{{ t.trade_id }}">${{ "{:,.2f}".format(t.current_price) }}</td>
                            <td>{{ t.volume }} oz</td>
                            <td id="pnl-{{ t.trade_id }}" class="{% if t.floating_pnl >= 0 %}profit{% else %}loss{% endif %}">
                                ${{ "{:,.2f}".format(t.floating_pnl) }}
                            </td>
                            <td id="margin-{{ t.trade_id }}">{{ t.margin_level_percent }}%</td>
                            <td>
                                <span id="status-{{ t.trade_id }}" style="padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; background-color: {% if t.status == 'HEALTHY' %}#00e676{% else %}#ff1744{% endif %}; color: #000;">
                                    {{ t.status }}
                                </span>
                            </td>
                        </tr>
                    {% else %}
                        <tr><td colspan="9" style="color: #8a8a93; font-style: italic; text-align: center;">No persistent database records. Input a trade above to verify!</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

def calculate_metrics_payload():
    market_data = get_market_data()
    active_simulations = []
    alerts_triggered = []
    total_account_pnl = 0.0

    for asset, thresholds in target_alerts.items():
        if asset in market_data:
            curr = market_data[asset]["price"]
            if curr >= thresholds["high"]:
                alerts_triggered.append(f"🚨 ALERT: {asset} broke resistance at ${thresholds['high']}!")
            elif curr <= thresholds["low"]:
                alerts_triggered.append(f"🚨 ALERT: {asset} dropped below support at ${thresholds['low']}!")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM positions")
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        asset = row["asset"]
        if asset in market_data:
            current = market_data[asset]["price"]
            entry = row["entry_price"]
            size = row["volume"]
            
            if row["type"] == "BUY":
                pnl = (current - entry) * size
            else:
                pnl = (entry - current) * size
                
            total_account_pnl += pnl
            equity = row["allocated_margin"] + pnl
            margin_level = (equity / row["allocated_margin"]) * 100
            
            active_simulations.append({
                "trade_id": row["id"],
                "asset": asset,
                "direction": row["type"],
                "entry_price": entry,
                "current_price": current,
                "volume": size,
                "floating_pnl": pnl,
                "margin_level_percent": round(margin_level, 1),
                "status": "STOP-OUT" if margin_level <= 50.0 else "HEALTHY"
            })

    return market_data, active_simulations, alerts_triggered, total_account_pnl

# -------------------------------------------------------------
# APP ROUTES
# -------------------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    market_data, active_simulations, alerts_triggered, total_account_pnl = calculate_metrics_payload()
    return render_template_string(
        HTML_TEMPLATE, 
        market_prices=market_data, 
        active_trades=active_simulations, 
        alerts=alerts_triggered,
        total_pnl=total_account_pnl
    )

@app.route('/api/data', methods=['GET'])
def get_api_data():
    market_data, active_simulations, alerts_triggered, total_account_pnl = calculate_metrics_payload()
    flat_prices = {asset: {"price": info["price"], "trend": info["trend"], "sma": info["sma"]} for asset, info in market_data.items()}
    
    return jsonify({
        "market_prices": flat_prices,
        "active_simulations": active_simulations,
        "alerts_triggered": alerts_triggered,
        "total_portfolio_pnl": round(total_account_pnl, 2)
    })

@app.route('/add_trade', methods=['POST'])
def add_trade():
    asset = request.form["asset"]
    trade_type = request.form["type"]
    entry_price = float(request.form["entry_price"])
    volume = float(request.form["volume"])
    allocated_margin = float(request.form["allocated_margin"])

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO positions (asset, type, entry_price, volume, allocated_margin)
        VALUES (?, ?, ?, ?, ?)
    ''', (asset, trade_type, entry_price, volume, allocated_margin))
    conn.commit()
    conn.close()

    return render_template_string("<script>window.location.href='/';</script>")

# -------------------------------------------------------------
# DYNAMIC HOST ENTRY RULE
# -------------------------------------------------------------
if __name__ == "__main__":
    # Reads dynamic port environment variables from host server container architectures
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
