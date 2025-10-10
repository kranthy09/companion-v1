"""
project/auth/supabase_client.py

Authentication with Supabase Client.
"""
from supabase import create_client, Client
from project.config import settings

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_ANON_KEY
)

supabase_admin: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY
)
