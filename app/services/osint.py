import asyncio, subprocess, shodan
from app.core.config import SHODAN_KEY

async def deep_scan(target):
    # Maigret Subprocess
    try:
        proc = await asyncio.create_subprocess_exec(
            'maigret', target, '--json', 'simple', '--top-20',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=45)
        socials = stdout.decode() if stdout else "No social matches."
    except: socials = "Scan timeout."

    # Shodan logic
    infra = "N/A"
    if SHODAN_KEY and "." in target:
        try:
            api = shodan.Shodan(SHODAN_KEY)
            res = api.host(target)
            infra = f"Ports: {res['ports']}, OS: {res.get('os','N/A')}"
        except: infra = "No infra data."

    return f"SOCIALS:\n{socials}\n\nINFRASTRUCTURE:\n{infra}"
