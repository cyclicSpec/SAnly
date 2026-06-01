import sqlite3


class Storage:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS daily (
                code        TEXT,
                date        TEXT,
                open        REAL,
                close       REAL,
                high        REAL,
                low         REAL,
                volume      REAL,
                amount      REAL,
                ma5         REAL,
                ma10        REAL,
                ma20        REAL,
                ma60        REAL,
                macd_dif    REAL,
                macd_dea    REAL,
                macd_hist   REAL,
                rsi_14      REAL,
                k           REAL,
                d           REAL,
                j           REAL,
                PRIMARY KEY (code, date)
            );
            CREATE TABLE IF NOT EXISTS signals (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      TEXT,
                code    TEXT,
                type    TEXT,
                level   TEXT,
                detail  TEXT
            );
        """)

    def save_daily(self, code, data):
        self._conn.execute("""
            INSERT OR REPLACE INTO daily
            (code, date, open, close, high, low, volume, amount,
             ma5, ma10, ma20, ma60,
             macd_dif, macd_dea, macd_hist,
             rsi_14, k, d, j)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            code, data["date"],
            data["open"], data["close"], data["high"], data["low"],
            data["volume"], data["amount"],
            data.get("ma5"), data.get("ma10"), data.get("ma20"), data.get("ma60"),
            data.get("macd_dif"), data.get("macd_dea"), data.get("macd_hist"),
            data.get("rsi_14"), data.get("k"), data.get("d"), data.get("j"),
        ))
        self._conn.commit()

    def get_latest_daily(self, code):
        cursor = self._conn.execute("""
            SELECT * FROM daily WHERE code=? ORDER BY date DESC LIMIT 1
        """, (code,))
        row = cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))

    def get_avg_volume(self, code, days=5):
        rows = self._conn.execute("""
            SELECT volume FROM daily WHERE code=?
            ORDER BY date DESC LIMIT ?
        """, (code, days)).fetchall()
        if len(rows) < days:
            return None
        return sum(r[0] for r in rows) / days

    def save_signal(self, ts, code, stype, level, detail):
        self._conn.execute("""
            INSERT INTO signals (ts, code, type, level, detail)
            VALUES (?,?,?,?,?)
        """, (ts, code, stype, level, detail))
        self._conn.commit()

    def get_recent_signals(self, limit=20):
        rows = self._conn.execute("""
            SELECT ts, code, type, level, detail
            FROM signals ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return rows
