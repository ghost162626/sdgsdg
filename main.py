import os
import discord
from discord import Embed
from datetime import datetime, timedelta
import requests
import json
from keep_alive import keep_alive

# --- Configurações do bot ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

PREFIX = '!'

# --- Firebase ---
FIREBASE_URL = os.environ.get("FIREBASE_URL")

def get_raw_from_firebase(raw_id):
    try:
        response = requests.get(f"{FIREBASE_URL}/raws/{raw_id}.json")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Erro ao buscar raw: {e}")
    return None

def update_raw_in_firebase(raw_id, new_code):
    try:
        response = requests.put(f"{FIREBASE_URL}/raws/{raw_id}/code.json", data=json.dumps(new_code))
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao atualizar raw: {e}")
        return False

def parse_datetime(date_obj):
    return f'os.time({{day={date_obj.day}, month={date_obj.month}, year={date_obj.year}, hour={date_obj.hour}, min={date_obj.minute}}})'

def add_whitelist_to_code(existing_code, player_id, player_name, added_by, expires_date):
    if "return" in existing_code and "{" in existing_code:
        lines = existing_code.split('\n')
        new_lines = []
        added = False
        for i, line in enumerate(lines):
            new_lines.append(line)
            if line.strip() == "}" and not added:
                new_line = f'    ["{player_id}"] = {{type = "Usuário adm", expires = {parse_datetime(expires_date)}}},'
                new_lines.insert(i, new_line)
                added = True
        return '\n'.join(new_lines)
    else:
        return f'''-- Whitelist adicionada por {added_by}
-- Data: {datetime.now().strftime("%d/%m/%Y %H:%M")}

return {{
    ["{player_id}"] = {{type = "Usuário adm", expires = {parse_datetime(expires_date)}}},
}}'''

def remove_whitelist_from_code(existing_code, player_id):
    lines = existing_code.split('\n')
    new_lines = []
    skip_next = False
    for i, line in enumerate(lines):
        if f'["{player_id}"]' in line:
            skip_next = True
            continue
        elif skip_next and line.strip().startswith("}"):
            skip_next = False
            new_lines.append(line)
        elif not skip_next:
            new_lines.append(line)
    return '\n'.join(new_lines)

# --- Eventos ---
@client.event
async def on_ready():
    print(f'🤖 Bot conectado como {client.user}')
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="!help"))

@client.event
async def on_message(message):
    if message.author == client.user: return
    if not message.content.startswith(PREFIX): return

    args = message.content[len(PREFIX):].split()
    command = args[0].lower() if args else ""

    # ----------------- addwhitelist -----------------
    if command == "addwhitelist":
        try:
            raw_id = None
            player_id = None
            days = 30
            i = 1
            while i < len(args):
                if args[i] == "-player" and i + 1 < len(args):
                    player_id = args[i + 1]; i += 2
                elif args[i] == "-days" and i + 1 < len(args):
                    days = int(args[i + 1]); i += 2
                elif not raw_id:
                    raw_id = args[i]; i += 1
                else: i += 1

            if not raw_id or not player_id:
                embed = Embed(title="❌ Uso incorreto", description="`!addwhitelist <raw_id> -player <playerId> -days <dias>`", color=0xff0000)
                await message.reply(embed=embed)
                return

            raw_data = get_raw_from_firebase(raw_id)
            if not raw_data:
                embed = Embed(title="❌ Raw não encontrado", description=f"ID `{raw_id}` não encontrado.", color=0xff0000)
                await message.reply(embed=embed)
                return

            now = datetime.now()
            expires_date = now + timedelta(days=days)
            player_name = f"Player_{player_id}"
            current_code = raw_data.get("code", "")
            current_title = raw_data.get("title", "Raw sem título")
            new_code = add_whitelist_to_code(current_code, player_id, player_name, str(message.author), expires_date)
            success = update_raw_in_firebase(raw_id, new_code)
            if not success:
                embed = Embed(title="❌ Erro Firebase", description="Não foi possível atualizar o raw.", color=0xff0000)
                await message.reply(embed=embed)
                return

            embed1 = Embed(title="✅ Whitelist Adicionada", color=0x00ff00, timestamp=now)
            embed1.add_field(name="📝 Raw", value=f"`{current_title}`", inline=True)
            embed1.add_field(name="🆔 Raw ID", value=f"`{raw_id}`", inline=True)
            embed1.add_field(name="🎮 Player ID", value=f"`{player_id}`", inline=True)
            embed1.add_field(name="👤 Player Name", value=player_name, inline=True)
            embed1.add_field(name="⏰ Expira em", value=f"<t:{int(expires_date.timestamp())}:R>", inline=True)
            embed1.add_field(name="📝 Adicionado por", value=str(message.author), inline=True)
            embed1.set_footer(text="CodeRaw 2025 - Sistema de Whitelist")

            new_whitelist_line = f'    ["{player_id}"] = {{type = "Usuário adm", expires = {parse_datetime(expires_date)}}},'
            code_preview = f"-- Linha adicionada:\n{new_whitelist_line}"
            embed2 = Embed(title="📄 Whitelist Adicionada", description=f"```lua\n{code_preview}\n```", color=0x0099ff, timestamp=now)

            await message.reply(embeds=[embed1, embed2])
        except Exception as e:
            print(f"Erro: {e}")
            embed = Embed(title="❌ Erro", description=f"{e}", color=0xff0000)
            await message.reply(embed=embed)

    # ----------------- removewhitelist -----------------
    elif command == "removewhitelist":
        try:
            raw_id = None
            player_id = None
            i = 1
            while i < len(args):
                if args[i] == "-player" and i + 1 < len(args):
                    player_id = args[i + 1]; i += 2
                elif not raw_id:
                    raw_id = args[i]; i += 1
                else: i += 1

            if not raw_id or not player_id:
                embed = Embed(title="❌ Uso incorreto", description="`!removewhitelist <raw_id> -player <playerId>`", color=0xff0000)
                await message.reply(embed=embed)
                return

            raw_data = get_raw_from_firebase(raw_id)
            if not raw_data:
                embed = Embed(title="❌ Raw não encontrado", description=f"ID `{raw_id}` não encontrado.", color=0xff0000)
                await message.reply(embed=embed)
                return

            current_code = raw_data.get("code", "")
            current_title = raw_data.get("title", "Raw sem título")
            new_code = remove_whitelist_from_code(current_code, player_id)
            success = update_raw_in_firebase(raw_id, new_code)
            if not success:
                embed = Embed(title="❌ Erro Firebase", description="Não foi possível atualizar o raw.", color=0xff0000)
                await message.reply(embed=embed)
                return

            embed = Embed(title="✅ Whitelist Removida", color=0x00ff00, timestamp=datetime.now())
            embed.add_field(name="📝 Raw", value=current_title, inline=True)
            embed.add_field(name="🆔 Raw ID", value=f"`{raw_id}`", inline=True)
            embed.add_field(name="🎮 Player ID", value=f"`{player_id}`", inline=True)
            embed.add_field(name="🗑️ Removido por", value=str(message.author), inline=True)
            embed.set_footer(text="CodeRaw 2025 - Sistema de Whitelist")
            await message.reply(embed=embed)
        except Exception as e:
            print(f"Erro: {e}")
            embed = Embed(title="❌ Erro", description=f"{e}", color=0xff0000)
            await message.reply(embed=embed)

    # ----------------- viewraw -----------------
    elif command == "viewraw":
        if len(args) < 2:
            await message.reply("❌ **Uso:** `!viewraw <raw_id>`")
            return
        raw_id = args[1]
        try:
            raw_data = get_raw_from_firebase(raw_id)
            if not raw_data:
                await message.reply("❌ Raw não encontrado.")
                return
            embed = Embed(title=f"📄 {raw_data.get('title','Raw')}", color=0x0099ff, timestamp=datetime.now())
            embed.add_field(name="🆔 ID", value=f"`{raw_id}`", inline=True)
            embed.add_field(name="👤 Autor", value=raw_data.get("authorName","Desconhecido"), inline=True)
            embed.add_field(name="👀 Views", value=raw_data.get("views",0), inline=True)
            code = raw_data.get("code","")
            code_preview = code if len(code)<=1000 else code[:1000]+"..."
            code_embed = Embed(title="📄 Código", description=f"```lua\n{code_preview}\n```", color=0xffa500, timestamp=datetime.now())
            await message.reply(embeds=[embed, code_embed])
        except Exception as e:
            print(f"Erro: {e}")
            await message.reply("❌ Erro ao buscar raw.")

    # ----------------- listwhitelist -----------------
    elif command == "listwhitelist":
        if len(args)<2:
            await message.reply("❌ **Uso:** `!listwhitelist <raw_id>`")
            return
        raw_id = args[1]
        try:
            raw_data = get_raw_from_firebase(raw_id)
            if not raw_data:
                await message.reply("❌ Raw não encontrado.")
                return
            code = raw_data.get("code","")
            lines = code.split('\n')
            whitelist_entries = [line.split('["')[1].split('"]')[0] for line in lines if '["' in line and 'type = "Usuário adm"' in line]
            embed = Embed(title=f"📋 Whitelist - {raw_data.get('title','Raw')}", color=0x7289da, timestamp=datetime.now())
            if whitelist_entries:
                embed.description = f"**Total de usuários:** {len(whitelist_entries)}"
                users_text = "\n".join([f"• `{u}`" for u in whitelist_entries[:10]])
                if len(whitelist_entries)>10: users_text+=f"\n... e mais {len(whitelist_entries)-10} usuários"
                embed.add_field(name="👥 Usuários", value=users_text, inline=False)
            else: embed.description="Nenhum usuário na whitelist."
            embed.set_footer(text=f"Raw ID: {raw_id}")
            await message.reply(embed=embed)
        except Exception as e:
            print(f"Erro: {e}")
            await message.reply("❌ Erro ao listar whitelist.")

    # ----------------- help -----------------
    elif command == "help":
        embed = Embed(title="🤖 Comandos do CodeRaw Whitelist Bot", color=0x7289da, timestamp=datetime.now())
        embed.description="Sistema de gerenciamento de whitelist em raws"
        embed.add_field(name="➕ Adicionar Whitelist", value="`!addwhitelist <raw_id> -player <playerId> -days <dias>`", inline=False)
        embed.add_field(name="🗑️ Remover Whitelist", value="`!removewhitelist <raw_id> -player <playerId>`", inline=False)
        embed.add_field(name="📋 Listar Whitelist", value="`!listwhitelist <raw_id>`", inline=False)
        embed.add_field(name="👀 Ver Raw", value="`!viewraw <raw_id>`", inline=False)
        embed.set_footer(text="CodeRaw 2025 - Sistema de Whitelist")
        await message.reply(embed=embed)

# --- Roda bot no Replit ---
if __name__ == "__main__":
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    client.run(token)
