import asyncio,asyncpg,os
from dotenv import load_dotenv
load_dotenv()
async def f():
 c=await asyncpg.connect(os.getenv('DATABASE_URL'))
 await c.execute("UPDATE tasks SET internal_status='completed',cooldown_until=NULL WHERE tasks_id=9")
 await c.close()
asyncio.run(f())

