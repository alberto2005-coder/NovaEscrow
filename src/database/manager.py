import aiosqlite
from datetime import datetime

class Database:
    def __init__(self, db_path="escrow_bot.db"):
        self.db_path = db_path
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    creator_id INTEGER NOT NULL,
                    counterparty_id INTEGER,
                    sender_id INTEGER,
                    receiver_id INTEGER,
                    amount REAL,
                    currency TEXT,
                    escrow_address TEXT,
                    receiver_wallet_address TEXT,
                    sender_refund_address TEXT,
                    transaction_hash TEXT,
                    confirmations_received INTEGER DEFAULT 0,
                    dispute_status TEXT,
                    dispute_mediator_id INTEGER,
                    dispute_reason TEXT,
                    status TEXT DEFAULT 'abierto',
                    ticket_number INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    ticket_counter INTEGER DEFAULT 0
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    total_volume_usd REAL DEFAULT 0.0,
                    average_rating REAL DEFAULT 0.0,
                    total_ratings INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, guild_id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    amount REAL DEFAULT 0.0,
                    UNIQUE(user_id, guild_id, currency)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    rater_id INTEGER NOT NULL,
                    rated_id INTEGER NOT NULL,
                    stars INTEGER NOT NULL,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            print("✅ Base de datos inicializada")
    
    async def create_ticket(self, channel_id, guild_id, creator_id, ticket_number):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO tickets (channel_id, guild_id, creator_id, ticket_number, status)
                VALUES (?, ?, ?, ?, 'abierto')
            """, (channel_id, guild_id, creator_id, ticket_number))
            await db.commit()
    
    async def get_ticket(self, channel_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM tickets WHERE channel_id = ?
            """, (channel_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None
    
    async def update_ticket(self, channel_id, **kwargs):
        valid_fields = ['counterparty_id', 'sender_id', 'receiver_id', 'amount', 'currency', 
                       'escrow_address', 'receiver_wallet_address', 'sender_refund_address',
                       'transaction_hash', 'confirmations_received', 'dispute_status', 
                       'dispute_mediator_id', 'dispute_reason', 'status']
        
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in valid_fields:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return
        
        values.append(datetime.utcnow().isoformat())
        values.append(channel_id)
        
        query = f"""
            UPDATE tickets 
            SET {', '.join(updates)}, updated_at = ?
            WHERE channel_id = ?
        """
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, values)
            await db.commit()
    
    async def delete_ticket(self, channel_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM tickets WHERE channel_id = ?", (channel_id,))
            await db.commit()
    
    async def get_next_ticket_number(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT ticket_counter FROM guild_settings WHERE guild_id = ?
            """, (guild_id,)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    next_number = row[0] + 1
                    await db.execute("""
                        UPDATE guild_settings SET ticket_counter = ? WHERE guild_id = ?
                    """, (next_number, guild_id))
                else:
                    next_number = 1
                    await db.execute("""
                        INSERT INTO guild_settings (guild_id, ticket_counter) VALUES (?, ?)
                    """, (guild_id, next_number))
                
                await db.commit()
                return next_number
    
    async def get_guild_stats(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT COUNT(*) FROM tickets WHERE guild_id = ?
            """, (guild_id,)) as cursor:
                result = await cursor.fetchone()
                total = result[0] if result else 0
            
            async with db.execute("""
                SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND status = 'completado'
            """, (guild_id,)) as cursor:
                result = await cursor.fetchone()
                completed = result[0] if result else 0
            
            async with db.execute("""
                SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND status != 'completado'
            """, (guild_id,)) as cursor:
                result = await cursor.fetchone()
                active = result[0] if result else 0
            
            return {
                'total_tickets': total,
                'completed_tickets': completed,
                'active_tickets': active
            }
    
    async def get_user_profile(self, user_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM users WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                
                await db.execute("""
                    INSERT INTO users (user_id, guild_id) VALUES (?, ?)
                """, (user_id, guild_id))
                await db.commit()
                
                return {
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'total_trades': 0,
                    'total_volume_usd': 0.0,
                    'average_rating': 0.0,
                    'total_ratings': 0
                }
    
    async def get_user_balance(self, user_id, guild_id, currency):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT amount FROM balances WHERE user_id = ? AND guild_id = ? AND currency = ?
            """, (user_id, guild_id, currency)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0.0
    
    async def update_balance(self, user_id, guild_id, currency, amount):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO balances (user_id, guild_id, currency, amount)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id, currency) 
                DO UPDATE SET amount = amount + ?
            """, (user_id, guild_id, currency, amount, amount))
            await db.commit()
    
    async def add_rating(self, ticket_id, rater_id, rated_id, stars, comment=None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO ratings (ticket_id, rater_id, rated_id, stars, comment)
                VALUES (?, ?, ?, ?, ?)
            """, (ticket_id, rater_id, rated_id, stars, comment))
            await db.commit()
            
            async with db.execute("""
                SELECT AVG(stars), COUNT(*) FROM ratings WHERE rated_id = ?
            """, (rated_id,)) as cursor:
                avg_rating, total = await cursor.fetchone()
                
            ticket = await self.get_ticket(ticket_id)
            await db.execute("""
                UPDATE users 
                SET average_rating = ?, total_ratings = ?
                WHERE user_id = ? AND guild_id = ?
            """, (avg_rating or 0.0, total or 0, rated_id, ticket['guild_id']))
            await db.commit()
    
    async def increment_trade_stats(self, user_id, guild_id, volume_usd):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET total_trades = total_trades + 1,
                    total_volume_usd = total_volume_usd + ?
                WHERE user_id = ? AND guild_id = ?
            """, (volume_usd, user_id, guild_id))
            await db.commit()
    
    async def get_all_balances(self, user_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT currency, amount FROM balances 
                WHERE user_id = ? AND guild_id = ? AND amount > 0
            """, (user_id, guild_id)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
