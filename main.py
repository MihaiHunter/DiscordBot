import discord
from discord.ext import commands
import pymongo
import os
from flask import Flask
from threading import Thread

# === Pornire server Flask pentru uptime ===
app = Flask('')

@app.route('/')
def home():
    return "Botul e online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# === Configurare bot ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# === Conectare la MongoDB Atlas ===
try:
    mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"))
    print("✅ Conectat la MongoDB Atlas.")
except pymongo.errors.ServerSelectionTimeoutError as e:
    print(f"❌ Eroare MongoDB: {e}")
    exit(1)

# === Baza de date ===
db = mongo_client["discord-bot"]
collection = db["channels"]

CREATE_CHANNEL_NAME = "CREATE NEW CHANNEL"

def clear_all_channel_data():
    try:
        collection.delete_many({})
        print("🧹 Canalele au fost curățate din DB.")
    except Exception as e:
        print(f"❌ Eroare curățare DB: {e}")

def get_user_channel_data(user_id):
    try:
        return collection.find_one({"user_id": user_id})
    except Exception as e:
        print(f"❌ Eroare acces DB: {e}")
        return None

def save_channel_data(user_id, channel_id, name, drag_and_drop, visibility):
    try:
        data = {
            "channel_id": channel_id,
            "channel_name": name,
            "drag_and_drop": drag_and_drop,
            "visibility": visibility
        }
        collection.update_one({"user_id": user_id}, {"$set": data}, upsert=True)
        print(f"✅ Salvat {user_id}: {data}")
    except Exception as e:
        print(f"❌ Eroare salvare: {e}")

def get_channel_properties(channel):
    everyone_role = channel.guild.default_role
    perms = channel.permissions_for(everyone_role)
    return perms.move_members, perms.view_channel

@bot.event
async def on_ready():
    print(f"✅ {bot.user} este online!")
    clear_all_channel_data()

    for guild in bot.guilds:
        verified = discord.utils.get(guild.roles, name="Verified")
        if not verified:
            verified = await guild.create_role(name="Verified")
            print("✅ Rol 'Verified' creat.")

        rules_channel = discord.utils.get(guild.text_channels, name="regulament-si-drepturi")
        if not rules_channel:
            rules_channel = await guild.create_text_channel('regulament-si-drepturi')
            print("✅ Canal 'regulament-si-drepturi' creat.")

        role_names = ["BAIAT", "FATA", "sub 1.60", "161-170", "1,71-180", "peste 1.81", "Singur", "In Relatie", "Indisponibil"]
        for role_name in role_names:
            if not discord.utils.get(guild.roles, name=role_name):
                await guild.create_role(name=role_name)
                print(f"✅ Rol '{role_name}' creat.")

        found_regulament = False
        async for message in rules_channel.history(limit=10):
            if message.content.startswith("**Regulament:**"):
                bot.regulament_message_id = message.id
                found_regulament = True
                break

        if not found_regulament:
            mesaj = await rules_channel.send("""
**Regulament:**

1. Tratați pe toată lumea cu respect. Fără sexism, rasism sau hate speech.
2. Fără content NSFW.
3. Fără reclame.
4. Dacă ceva e suspect pe voice/DM, scrie unui admin.
5. Fără politică/religie.
6. Dacă ești banat, înseamnă că ai greșit grav.
7. Respectați GDPR-ul.

✅ Reacționează cu ✔️ pentru a primi acces complet la server.
            """)
            await mesaj.add_reaction("✔️")
            bot.regulament_message_id = mesaj.id

@bot.event
async def on_raw_reaction_add(payload):
    if hasattr(bot, 'regulament_message_id') and payload.message_id == bot.regulament_message_id:
        if str(payload.emoji) == "✔️":
            guild = bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            role = discord.utils.get(guild.roles, name="Verified")
            if role and member:
                await member.add_roles(role)
                print(f"✅ Rol 'Verified' acordat lui {member.display_name}")

@bot.event
async def on_raw_reaction_remove(payload):
    if hasattr(bot, 'regulament_message_id') and payload.message_id == bot.regulament_message_id:
        if str(payload.emoji) == "✔️":
            guild = bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            role = discord.utils.get(guild.roles, name="Verified")
            if role and member:
                await member.remove_roles(role)
                print(f"🗑️ Rol 'Verified' eliminat de la {member.display_name}")

@bot.event
async def on_member_join(member):
    welcome = discord.utils.get(member.guild.text_channels, name="welcome")
    if welcome:
        await welcome.send(f"Bun venit, {member.mention}! Reacționează cu ✔️ în #regulament-si-drepturi.")

@bot.event
async def on_member_remove(member):
    welcome = discord.utils.get(member.guild.text_channels, name="welcome")
    if welcome:
        await welcome.send(f"{member.name} a părăsit serverul. 😢")

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.name == CREATE_CHANNEL_NAME:
        guild = member.guild
        user_data = get_user_channel_data(member.id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False),
            member: discord.PermissionOverwrite(connect=True, manage_channels=True, move_members=True, administrator=True)
        }

        if user_data:
            channel_name = user_data.get("channel_name", f"{member.name}'s Channel")
            drag_and_drop = user_data.get("drag_and_drop", False)
            visibility = user_data.get("visibility", True)
        else:
            channel_name = f"{member.name}'s Channel"
            drag_and_drop, visibility = get_channel_properties(after.channel)

        new_channel = await guild.create_voice_channel(name=channel_name, overwrites=overwrites, category=after.channel.category)
        await set_permissions_for_channel(new_channel, drag_and_drop, visibility)
        save_channel_data(member.id, new_channel.id, channel_name, drag_and_drop, visibility)
        await member.move_to(new_channel)

    if before.channel and len(before.channel.members) == 0:
        user_data = get_user_channel_data(member.id)
        if user_data and before.channel.id == user_data.get("channel_id"):
            drag_and_drop, visibility = get_channel_properties(before.channel)
            save_channel_data(member.id, before.channel.id, before.channel.name, drag_and_drop, visibility)
            await before.channel.delete()

async def set_permissions_for_channel(channel, drag_and_drop, visibility):
    everyone_role = channel.guild.default_role
    await channel.set_permissions(everyone_role, overwrite=discord.PermissionOverwrite(
        move_members=drag_and_drop, view_channel=visibility))

# === Pornire bot ===
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
