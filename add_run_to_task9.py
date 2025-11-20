import asyncio,asyncpg,os
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
async def f():
 c=await asyncpg.connect(os.getenv('DATABASE_URL'))
 run_id=await c.fetchval("INSERT INTO task_runs (task_id,status,started_at,completed_at) VALUES (9,'completed',$1,$2) RETURNING tasks_runs_id", datetime.now(timezone.utc), datetime.now(timezone.utc))
 await c.execute("UPDATE tasks SET last_run_id=$1 WHERE tasks_id=9", run_id)
 print(f"✅ Workflow run créé: run_id={run_id} pour task_id=9")
 await c.close()
asyncio.run(f())

