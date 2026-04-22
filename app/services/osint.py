import asyncio, os
import shodan, whois, dns.resolver
from duckduckgo_search import DDGS
from serpapi import GoogleSearch
from app.core.config import SHODAN_KEY, SERPAPI_KEY, MAIGRET_BIN

def sync_whois(target):
    try:
        w = whois.whois(target)
        return f"Registrar: {w.registrar}, Creation: {w.creation_date}"
    except: return "N/A"

def sync_dns(target):
    try:
        ans = dns.resolver.resolve(target, 'A')
        return ", ".join([ip.address for ip in ans])
    except: return "N/A"

def sync_ddg(target):
    try:
        with DDGS() as ddgs:
            return "\n".join([r.get('body', '') for r in ddgs.text(target, max_results=3)])
    except: return ""

def sync_shodan(target):
    if not SHODAN_KEY or not ("." in target or target.isdigit()): return "N/A"
    try:
        api = shodan.Shodan(SHODAN_KEY)
        h = api.host(target)
        return f"Ports: {h.get('ports', [])}, OS: {h.get('os', 'N/A')}, Vulns: {h.get('vulns', [])}"
    except: return "N/A"

async def run_maigret(target, is_pro=False):
    top = 500 if is_pro else 30
    cmd = f"{MAIGRET_BIN} {target} --json simple --top-{top} --timeout 15"
    try:
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=40)
        return out.decode('utf-8', errors='ignore') if out else "No data."
    except asyncio.TimeoutError:
        proc.kill()
        return "[TIMEOUT] Соціальні мережі проаналізовано частково."
    except: return "Error"

async def execute_osint(target: str, is_pro: bool = False):
    tasks = [
        asyncio.to_thread(sync_ddg, target),
        asyncio.to_thread(sync_shodan, target),
        asyncio.to_thread(sync_whois, target),
        asyncio.to_thread(sync_dns, target),
        run_maigret(target, is_pro)
    ]
    r_ddg, r_sh, r_whois, r_dns, r_maigret = await asyncio.gather(*tasks)
    
    return f"""
    --- WEB & DNS ---
    DDG: {r_ddg[:500]}
    DNS (A): {r_dns}
    WHOIS: {r_whois}
    --- INFRASTRUCTURE ---
    SHODAN: {r_sh}
    --- SOCIAL FOOTPRINT ---
    MAIGRET: {r_maigret[:800]}
    """
