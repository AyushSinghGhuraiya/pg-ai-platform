"""Fetch the first tenant ID from Supabase. Reads credentials from .env."""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

async def main():
    from config import settings
    from supabase._async.client import create_client
    client = await create_client(settings.supabase_url, settings.supabase_service_key)
    r = await client.table('tenants').select('id,business_name').limit(1).execute()
    for row in r.data:
        print("TENANT_ID=" + row['id'])
        print("NAME=" + row['business_name'])

asyncio.run(main())
