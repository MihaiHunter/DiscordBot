from pyngrok import ngrok, conf
import discord
from discord.ext import commands
import pymongo
import os
from flask import Flask
from threading import Thread

# Intenții Discord
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
conf.get_default(
).auth_token = "30FdPuN27Zk6TDPg2ThZ0OpVCBS_5LAtFbVP4n2TcPaSLdHmV"
# === FLASK SERVER pentru UPTIMEROBOT ===
app = Flask('')


@app.route('/')
def home():
    return "Botul e online!"


def run():
    public_url = ngrok.connect(8080)
    print(f"🌐 URL public generat de ngrok: {public_url}")
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


# Conectare la MongoDB Atlas
try:
    mongo_client = pymongo.MongoClient(
        "mongodb+srv://mys3mihai:Nt0MLNJ9O7G0DKNW@cluster0.ztmjt6k.mongodb.net/?retryWrites=true&w=majority&ssl=true"
    )
    print("Conexiunea la MongoDB Atlas a fost realizată cu succes!")
except pymongo.errors.ServerSelectionTimeoutError as e:
    print(f"Eroare la conectarea la MongoDB: {e}")
    exit(1)

# Baza de date și colecția
db = mongo_client["discord-bot"]
collection = db["channels"]

CREATE_CHANNEL_NAME = "CREATE NEW CHANNEL"


# Curățare canale salvate
def clear_all_channel_data():
    try:
        collection.delete_many({})
        print(
            "Toate informațiile despre canale au fost șterse din baza de date."
        )
    except Exception as e:
        print(f"Eroare la ștergerea datelor din MongoDB: {e}")


def get_user_channel_data(user_id):
    try:
        return collection.find_one({"user_id": user_id})
    except Exception as e:
        print(f"Eroare la accesarea datelor pentru user {user_id}: {e}")
        return None


def save_channel_data(user_id, channel_id, name, drag_and_drop, visibility):
    try:
        data = {
            "channel_id": channel_id,
            "channel_name": name,
            "drag_and_drop": drag_and_drop,
            "visibility": visibility
        }
        collection.update_one({"user_id": user_id}, {"$set": data},
                              upsert=True)
        print(f"Datele pentru {user_id} au fost actualizate: {data}")
    except Exception as e:
        print(f"Eroare la salvarea datelor: {e}")


def get_channel_properties(channel):
    drag_and_drop = False
    visibility = False
    everyone_role = channel.guild.default_role

    perms = channel.permissions_for(everyone_role)
    drag_and_drop = perms.move_members
    visibility = perms.view_channel
    return drag_and_drop, visibility


@bot.event
async def on_ready():
    print(f"{bot.user} este online!")
    clear_all_channel_data()

    for guild in bot.guilds:
        verified = discord.utils.get(guild.roles, name="Verified")
        if not verified:
            continue
        for channel in guild.channels:
            if channel.name in ["welcome", "regulament-si-drepturi"]:
                await channel.set_permissions(guild.default_role,
                                              view_channel=True)
            else:
                await channel.set_permissions(guild.default_role,
                                              view_channel=False)
                await channel.set_permissions(verified, view_channel=True)


@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.name == CREATE_CHANNEL_NAME:
        guild = member.guild
        user_data = get_user_channel_data(member.id)

        overwrites = {
            guild.default_role:
            discord.PermissionOverwrite(connect=False),
            member:
            discord.PermissionOverwrite(connect=True,
                                        manage_channels=True,
                                        move_members=True,
                                        administrator=True)
        }

        if user_data:
            channel_name = user_data.get("channel_name",
                                         f"{member.name}'s Channel")
            drag_and_drop = user_data.get("drag_and_drop", False)
            visibility = user_data.get("visibility", True)
        else:
            channel_name = f"{member.name}'s Channel"
            drag_and_drop, visibility = get_channel_properties(after.channel)

        new_channel = await guild.create_voice_channel(
            name=channel_name,
            overwrites=overwrites,
            category=after.channel.category)
        await set_permissions_for_channel(new_channel, drag_and_drop,
                                          visibility)
        save_channel_data(member.id, new_channel.id, channel_name,
                          drag_and_drop, visibility)
        await member.move_to(new_channel)

    if before.channel and len(before.channel.members) == 0:
        user_data = get_user_channel_data(member.id)
        if user_data and before.channel.id == user_data.get("channel_id"):
            drag_and_drop, visibility = get_channel_properties(before.channel)
            save_channel_data(member.id, before.channel.id,
                              before.channel.name, drag_and_drop, visibility)
            await before.channel.delete()


async def set_permissions_for_channel(channel, drag_and_drop, visibility):
    everyone_role = channel.guild.default_role
    await channel.set_permissions(everyone_role,
                                  overwrite=discord.PermissionOverwrite(
                                      move_members=drag_and_drop,
                                      view_channel=visibility))


@bot.event
async def on_member_join(member):
    welcome = discord.utils.get(member.guild.text_channels, name="welcome")
    if welcome:
        await welcome.send(
            f"Bun venit, {member.mention}! Reacționează cu ✔️ în #regulament-si-drepturi pentru acces complet!"
        )


@bot.event
async def on_member_remove(member):
    welcome = discord.utils.get(member.guild.text_channels, name="welcome")
    if welcome:
        await welcome.send(f"{member.name} a părăsit serverul. 😢")


@bot.event
async def on_ready():
    print(f"{bot.user} este online!")

    for guild in bot.guilds:
        # Verifică și creează rolul Verified dacă nu există
        verified = discord.utils.get(guild.roles, name="Verified")
        if not verified:
            verified = await guild.create_role(name="Verified")
            print("✅ Rol 'Verified' a fost creat.")

        # Creează canalul 'regulament-si-drepturi' dacă nu există
        rules_channel = discord.utils.get(guild.text_channels,
                                          name="regulament-si-drepturi")
        if not rules_channel:
            rules_channel = await guild.create_text_channel(
                'regulament-si-drepturi')
            print("✅ Canal 'regulament-si-drepturi' a fost creat.")

        # Creează lista de roluri personalizate
        role_names = [
            "BAIAT", "FATA", "sub 1.60", "161-170", "1,71-180", "peste 1.81",
            "Singur", "In Relatie", "Indisponibil"
        ]

        for role_name in role_names:
            existing_role = discord.utils.get(guild.roles, name=role_name)
            if not existing_role:
                try:
                    await guild.create_role(name=role_name)
                    print(f"✅ Rol creat: {role_name}")
                except Exception as e:
                    print(f"❌ Eroare la crearea rolului {role_name}: {e}")

        # Verifică dacă regulamentul a fost deja trimis
        found_regulament = False
        async for message in rules_channel.history(limit=10):
            if message.content.startswith("**Regulament:**"):
                bot.regulament_message_id = message.id  # salvează ID-ul mesajului existent
                found_regulament = True
                break

        # Trimite regulamentul și adaugă reacție dacă nu există deja
        if not found_regulament:
            mesaj = await rules_channel.send("""
**Regulament:**

1. Tratați pe toată lumea cu respect. Fără sexism, rasism sau hate speech. "ma-ta" e interzis.
2. Fără content NSFW.
3. Fără reclame.
4. Dacă ceva e suspect pe voice/DM, scrie unui admin.
5. Fără politică/religie.
6. Dacă ești banat, înseamnă că ai greșit grav.
7. Respectați GDPR-ul.

✅ Reacționează cu ✔️ pentru a primi acces complet la server.
                """)
            await mesaj.add_reaction("✔️")
            bot.regulament_message_id = mesaj.id  # salvează ID-ul mesajului nou

    @bot.event
    async def on_raw_reaction_add(payload):
        if hasattr(bot, 'regulament_message_id'
                   ) and payload.message_id == bot.regulament_message_id:
            if str(payload.emoji) == "✔️":
                guild = bot.get_guild(payload.guild_id)
                member = guild.get_member(payload.user_id)
                role = discord.utils.get(guild.roles, name="Verified")
                if role and member:
                    await member.add_roles(role)
                    print(
                        f"✅ Rol 'Verified' acordat lui {member.display_name}")

    @bot.event
    async def on_raw_reaction_remove(payload):
        if hasattr(bot, 'regulament_message_id'
                   ) and payload.message_id == bot.regulament_message_id:
            if str(payload.emoji) == "✔️":
                guild = bot.get_guild(payload.guild_id)
                member = guild.get_member(payload.user_id)
                role = discord.utils.get(guild.roles, name="Verified")
                if role and member:
                    await member.remove_roles(role)
                    print(
                        f"🗑️ Rol 'Verified' eliminat de la {member.display_name}"
                    )


# PORNEȘTE SERVERUL KEEP-ALIVE ȘI BOTUL
keep_alive()
bot.run(os.getenv("MTM5NjQzNzAyNDI4MTcyMjk1Mg.GAHMz8.JsqqW5JJhzBwlbL3m7eCAjmjqjVFVknDVVndfE"))
