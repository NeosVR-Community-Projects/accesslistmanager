#!/bin/python

import logging
import sqlite3
import traceback
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, Text, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

from disnake.ext import commands

from neos.client import Client
from neos.classes import LoginDetails

from config import DISCORD_BOT_TOKEN, NEOS_USERNAME, NEOS_PASSWORD

bot = commands.InteractionBot()

logging.basicConfig(filename='discord_bot.log', level=logging.DEBUG, format='%(levelname)s %(asctime)s %(message)s')

logger = logging.getLogger('discord')
handler = logging.FileHandler(filename='discord_usage.log', encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
logger.addHandler(handler)

client = Client()

client.login(
    LoginDetails(username=NEOS_USERNAME, password=NEOS_PASSWORD)
)


class User(Base):
    __tablename__ = 'neos_user'

    id = Column(Integer, primary_key=True)
    neos_username = Column(Text, unique=True, nullable=False)
    discord_username = Column(Text, nullable=False)
    discord_id = Column(Integer, nullable=False)
    verifier = Column(Text, nullable=False)
    verified_date = Column(DateTime, default=datetime.utcnow)

    def __init__(
            self, neos_username, discord_username, discord_id, verifier,
            verified_date = None
    ):
        self.neos_username = neos_username
        self.discord_username = discord_username
        self.discord_id = discord_id
        self.verifier = verifier
        if verified_date:
            self.verified_date = verified_date

    def __str__(self):
        return self.neos_username

    def __repr__(self):
        return self.__str__()

engine = create_engine('sqlite:///accesslist.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def user_exist(username):
    if username.startswith('U-'):
        neos_users = session.query(User).filter(User.neos_username == username)
    else:
        neos_users = session.query(User).filter(User.discord_username == username)
    return bool(
        neos_users.count()
    )

def log_action(inter, username, action):
        logger.warning(f'[{inter.guild.name}:{inter.guild.id}] [{inter.channel.name}:{inter.channel.id}] [{inter.author.display_name}:{inter.author.name}] - {action} {username}')

def send_cmd(cmd):
    client.sendMessageLegacy('U-USFN-Orion', 'U-Neos', cmd)
    msgs = client.getMessageLegacy(maxItems=10, user='U-Neos')
    try:
        cmd_index = next((i for (i, d) in enumerate(msgs) if d["content"] == cmd), None)
        resp_index = cmd_index - 1
        return msgs[resp_index]['content']
    except (TypeError, IndexError) as exc:
        print('Command user:')
        print(cmd)
        print('Last messages from U-Neos:')
        print(msgs)
        print(traceback.format_exc())
        raise ValueError('Something is wrong with the neos API, check the bot logs')

@bot.slash_command(description='Manage USFN AD accesslist')
async def accesslist(inter):
    pass

@accesslist.sub_command(name='add', description='Adds a new users to the cloud variable')
async def add(inter, neos_username: str, discord_username: str, discord_id: int):
    log_action(inter, neos_username, 'add')
    if not neos_username.startswith('U-'):
        await inter.response.send_message("Please be sure to precise the 'U-' before the neos username!")
        return
    elif "#" not in discord_username:
        await inter.response.send_message("The discord username must also have the discord tag!")
        return
    if not user_exist(neos_username):
        #await inter.response.send_message(f'/setGroupVarValue G-United-Space-Force-N orion.userAccess.bool {username} true')
        session.add(
            User(
                neos_username,
                discord_username,
                discord_id,
                inter.user.name + "#" + inter.user.tag,
            )
        )
        session.commit()

    await inter.response.send_message(
        f'User {neos_username} added to the acceptlist')

@accesslist.sub_command(
    name='remove',
    description='Removes an user, by `U-` neos or discord username from the cloud variable')
async def remove(inter, username: str):
    log_action(inter, username, 'remove')
    #await inter.response.send_message(f'/setGroupVarValue G-United-Space-Force-N orion.userAccess.bool {username} false')
    if user_exist(username):
        if username.startswith('U-'):
            neos_user = session.query(User).filter(User.neos_username == username)[0]
        else:
            neos_user = session.query(User).filter(User.discord_username == username)[0]
        session.delete(neos_user)
        session.commit()

    await inter.response.send_message(
        f'User {username} removed fromt the acceptlist')

@accesslist.sub_command(
    name='search',
    description='Returns if an user, by `U-` neos or discord username is in the cloud variable')
async def search(
        inter, username: str,
        type: str = commands.Param(
            choices={"User": "user", "Verifier": "verifier"})
    ):
    log_action(inter, username, 'search')
    if type == 'verifier':
        neos_users = session.query(User).filter(User.verifier == username)
        users = "".join([f" - {user}\n" for user in neos_users])
        formated_text = (
            f"{username} had accepted the following users in the past:\n"
            f"{users}"
        )
        await inter.response.send_message(formated_text)
    else:
        if user_exist(username):
            if username.startswith('U-'):
                neos_user = session.query(User).filter(User.neos_username == username)[0]
            else:
                neos_user = session.query(User).filter(User.discord_username == username)[0]
                username = neos_user.neos_username
            try:
                cloud_var = send_cmd(f'/getGroupVarValue G-United-Space-Force-N orion.userAccess {username}')
            except ValueError as exc:
                cloud_var = exc
            formated_text = (
                f"**Neos U- username:** {neos_user.neos_username}\n"
                f"**Discord username:** {neos_user.discord_username}\n"
                f"**Discord id:** {neos_user.discord_id}\n"
                f"**Verifier discord username:** {neos_user.verifier}\n"
                f"**Verification date:** {neos_user.verified_date} ({neos_user.verified_date})\n"
                f"**Cloud variable status:** {cloud_var}"
            )
            await inter.response.send_message(formated_text)
        else:
            username_type = "neos"
            if not username.startswith('U-'):
                username_type = "discord"
            await inter.response.send_message(
                f"No {username_type} user found for `{username}`")

bot.run(DISCORD_BOT_TOKEN)
