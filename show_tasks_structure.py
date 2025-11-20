import asyncio,asyncpg,os
from dotenv import load_dotenv
load_dotenv()
async def f():
 c=await asyncpg.connect(os.getenv('DATABASE_URL'))
 cols=await c.fetch("SELECT column_name,data_type FROM information_schema.columns WHERE table_name='tasks' ORDER BY ordinal_position")
 print('📋 Colonnes de la table tasks:')
 for col in cols: print(f"  - {col['column_name']}: {col['data_type']}")
 await c.close()
asyncio.run(f())

