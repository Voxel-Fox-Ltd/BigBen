import asyncio
from datetime import datetime as dt
import re
import collections
from typing import Dict, Union, Tuple, Optional

import discord
from discord.ext import tasks, vbu


class BongHandler(vbu.Cog):

    EMOJI_REGEX = re.compile(r"<a?:(?P<name>.+?):(?P<id>\d+?)>")
    DEFAULT_BONG_TEXT = "Bong"
    BONG_TEXT: Dict[Union[Tuple[int, int], Tuple[int, int, int]], str] = {
        (1, 1): "{0.year} Bong",
        (14, 2): "Valentine's Bong",
        (1, 4): "Bing",
        (22, 4): "Earth Bong",
        (2, 7): "Midway Bong",
        (6, 9): "Birthday Bong",
        (31, 10): "Spooky Bong",
        (25, 12): "Christmas Bong",

        (12, 4, 2020): "Easter Bong",
        (4, 4, 2021): "Easter Bong",
        (17, 4, 2022): "Easter Bong",
        (9, 4, 2023): "Easter Bong",
        (31, 3, 2024): "Easter Bong",
    }  # (DD, MM, YYYY?): Output

    def __init__(self, bot: vbu.Bot):
        super().__init__(bot)
        self.last_posted_hour: int = None
        # The last hour of bongs that was posted, used for checking if we should post a new one
        # `None` is valid as making sure the minute is 0 is also checked

        self.bing_bong.start()
        # The bong loop

        self.current_bong_messages = set()
        # Messages that the bot posted, used for checking if the button was clicked

        self.bong_handle_locks = collections.defaultdict(asyncio.Lock)
        # A lock instance so we don't handle the same bong twice

        self.bong_button_clicks = collections.defaultdict(set)
        # A dict of `message: {user_id, ...}` to count how many clicks the button has

        self.first_button_click = {}
        # A dict of message_id: username for the first people to click the bong button

    def cog_unload(self):
        self.bing_bong.cancel()

    @tasks.loop(seconds=1)
    async def bing_bong(self):
        """
        Do the bong.
        """

        # See if it should post
        now = dt.utcnow()
        if now.hour != self.last_posted_hour and now.minute == 0:
            self.last_posted_hour = now.hour
        else:
            return
        self.bot.dispatch("bong")

    async def send_guild_bong_message(
            self,
            text: str,
            now: dt,
            guild_id: int,
            settings: dict,
            guilds_to_delete: set):
        """
        An async function to send a bong message to the given guild.

        Parameters
        ----------
        text : str
            The text to send.
        now : datetime.datetime
            The current time.
        guild_id : int
            The ID of the guild to send the settings for.
        settings : dict
            The guild's settings.
        guilds_to_delete : set
            A set of guilds to delete. Not handled by this function, but outside of it.
            Can be added to.
        """

        avatar_url = f"https://raw.githubusercontent.com/Voxel-Fox-Ltd/BigBen/master/config/images/{now.hour % 12}.png"

        # Try for the guild
        try:

            # Lets set our channel ID here
            channel_id = settings['bong_channel_id']
            if channel_id is None:
                return

            # Can we hope we have a webhook?
            payload = {}
            if not settings.get("bong_channel_webhook"):
                return  # Death to channel sends

            # Grab webook
            webhook_url = settings.get("bong_channel_webhook")
            if not webhook_url:
                return
            url = webhook_url + "?wait=1"
            payload.update({
                "wait": True,
                "username": self.bot.user.name,
                "avatar_url": avatar_url,
            })

            # Set up our emoji to be added
            emoji = settings['bong_emoji']

            # See if we should get some other text
            override_text = settings.get('override_text', {}).get(f"{now.month}-{now.day}")
            payload['content'] = override_text or text

            # Set up the components to be added
            if emoji:
                payload['components'] = discord.ui.MessageComponents(
                    discord.ui.ActionRow(
                        discord.ui.Button(
                            custom_id="BONG MESSAGE BUTTON",
                            emoji=emoji,
                            style=discord.ButtonStyle.secondary,
                        )
                    )
                ).to_dict()

            # Send message
            try:
                site = await self.bot.session.post(url, json=payload)
                message_payload = await site.json()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
                try:
                    guilds_to_delete.add(guild_id)
                except:
                    pass
                self.logger.info(f"Send failed - {e} (G{guild_id}/C{channel_id})")
                return

            # Cache message
            self.current_bong_messages.add(int(message_payload['id']))
            self.logger.info(f"Sent bong message to channel (G{guild_id}/C{channel_id}/M{message_payload['id']})")

        except Exception as e:
            self.logger.info(f"Failed sending message to guild (G{guild_id}) - {e}")

    @vbu.Cog.listener("on_bong")
    async def do_bong(self, bong_guild_id: Optional[int] = None):
        """
        Dispatch the bong message.
        """

        # Get text
        now = dt.utcnow()
        text = self.BONG_TEXT.get(
            (now.day, now.month, now.year),
            self.BONG_TEXT.get(
                (now.day, now.month),
                self.DEFAULT_BONG_TEXT
            )
        ).format(now)
        self.logger.info(f"Sending bong message text '{text}'")

        # Clear caches
        guilds_to_delete = set()
        if bong_guild_id is None:
            self.current_bong_messages.clear()  # Clear for the reacted to bong first role

        # Set up what we need to wait for
        tasks_to_gather = []

        # Let's see our cached guilds
        for guild_id, settings in self.bot.guild_settings.copy().items():

            # See if we give a shit about this guild
            if bong_guild_id is not None and bong_guild_id != guild_id:
                continue

            # See if they have a webhook
            if settings.get("bong_channel_webhook"):
                tasks_to_gather.append(self.send_guild_bong_message(
                    text, now, guild_id, settings, guilds_to_delete,
                ))

        # Gather all of our data, send all the messages, etc
        await asyncio.gather(*tasks_to_gather)

        # Sick we're done
        self.logger.info("Done sending bong messages")

        # Delete channels that we should no longer care about
        async with self.bot.database() as db:
            await db(
                """UPDATE guild_settings SET bong_channel_id=NULL WHERE guild_id=ANY($1::BIGINT[])""",
                list(guilds_to_delete),
            )
        for guild_id in guilds_to_delete:
            self.bot.guild_settings[guild_id]['bong_channel_id'] = None

    async def update_bong_message_components(self, payload: discord.Interaction):
        """
        Update the components on a message to show the user click count.

        Parameters
        ----------
        payload : discord.Interaction
            A (not responded to) interaction that lets us update the bong message.
        """

        # Get the current components
        try:
            assert payload.message
            assert payload.message.components
        except AssertionError:
            return
        components = payload.message.components

        # Add the "first clicked by" button
        if len(components.components[0].components) == 1:
            username = str(payload.user)
            components.components[0].add_component(
                discord.ui.Button(
                    label=username,
                    custom_id="BONG MESSAGE FIRST CLICKED",
                    disabled=True,
                    style=discord.ButtonStyle.secondary
                )
            )

        # Update the bong button
        bong_button = components.get_component("BONG MESSAGE BUTTON")
        button_clicks = len(self.bong_button_clicks[payload.message.id])
        if button_clicks > 1:
            bong_button.label = f"{button_clicks} clicks"
        else:
            bong_button.label = f"{button_clicks} click"

        # Edit the message using the payload
        await payload.response.edit_message(components=components)
        # self.logger.info(f"Tried to update components on message {payload.message.id} - {r.status}")
        self.logger.info(f"Tried to update components on message {payload.message.id}")

    @vbu.Cog.listener()
    async def on_component_interaction(self, payload: discord.Interaction[str]):
        """
        Waits for the bong button to be pressed
        """

        # See if it's a bong button
        if payload.custom_id != "BONG MESSAGE BUTTON":
            return
        try:
            assert payload.message
            assert payload.user
        except AssertionError:
            return

        # Get the current times as something we can compare
        message_timestamp = payload.message.created_at
        message_time_serial = (
            message_timestamp.year,
            message_timestamp.month,
            message_timestamp.day,
            message_timestamp.hour,
        )
        now = dt.utcnow()
        now_serial = (
            now.year,
            now.month,
            now.day,
            now.hour,
        )

        # Check that the times are the same, so that the user can get good
        if message_time_serial != now_serial:

            # If the button is cached then we'll handle it
            if payload.message.id in self.bong_button_clicks and payload.message.id in self.first_button_click:
                await self.update_bong_message_components(payload)
                await payload.followup.send("You can't click a bong button from the past :<", ephemeral=True)
            else:
                await payload.response.send_message("You can't click a bong button from the past :<", ephemeral=True)
            return

        # Say that the user has clicked the button
        self.bong_button_clicks[payload.message.id].add(payload.user.id)  # Add this user to a list of clickers
        self.first_button_click.setdefault(payload.message.id, str(payload.user))  # Say this button was clicked first by user

        # Grab a lock so we can edit the message
        lock = self.bong_handle_locks[payload.message.id]

        # Try and get the lock
        response_text: str = ""
        try:
            if lock.locked():
                raise asyncio.TimeoutError()
            await asyncio.wait_for(lock.acquire(), timeout=0.5)

        # Can't get the lock, tell them they weren't first
        except asyncio.TimeoutError:
            response_text = "You weren't the first person to click the button :c"

        # We got the lock! Let's go gamer
        else:

            # See if it's in our list of unreacted-to messages
            if payload.message.id not in self.current_bong_messages:
                response_text = "This button has already been clicked :<"
            else:
                response_text = "You were the first to react! :D"
                await self.handle_bong_component(payload)
            lock.release()

        # And update the bong message
        await self.update_bong_message_components(payload)
        if response_text:
            await payload.followup.send(response_text, ephemeral=True)

    async def handle_bong_component(self, payload: discord.Interaction):
        """
        Handle a bong button being pressed for the first time
        """

        try:
            assert payload.message
            assert payload.user
        except AssertionError:
            return

        # Database handle
        self.logger.info(f"Guild {payload.guild_id} with user {payload.user.id} in {dt.utcnow() - discord.Object(payload.message.id).created_at}")
        self.current_bong_messages.discard(payload.message.id)  # We don't need to handle this one any more
        async with self.bot.database() as db:
            await db(
                """SELECT * FROM bong_log WHERE guild_id=$1 ORDER BY timestamp DESC LIMIT 1""",
                payload.guild_id,
            )
            await db(
                """INSERT INTO bong_log (guild_id, user_id, timestamp, message_timestamp) VALUES ($1, $2, $3, $4)""",
                payload.guild_id, payload.user.id, dt.utcnow(), discord.Object(payload.message.id).created_at,
            )

        # Don't manage roles for now
        return

        # # Check they have a role set up
        # role_id = self.bot.guild_settings[payload.guild_id]['bong_role_id']
        # if role_id is None:
        #     return

        # # Get the bong role
        # try:
        #     bong_role = guild.get_role(role_id)
        # except (IndexError, discord.HTTPException):
        #     bong_role = None
        # if bong_role is None:
        #     return self.logger.info(f"Bong role doesn't exist (G{guild.id})")

        # # See who currently has it
        # if current_bong_member_rows:
        #     current_bong_member_id = current_bong_member_rows[0]['user_id']
        #     try:
        #         current_bong_member = guild.get_member(current_bong_member_id) or await guild.fetch_member(current_bong_member_id)
        #     except discord.HTTPException:
        #         current_bong_member = None
        # else:
        #     current_bong_member = None

        # # See who we want to give it to
        # new_bong_member = guild.get_member(payload.user.id) or await guild.fetch_member(payload.user.id)

        # # See if we can remove the role from the people who have it
        # try:

        #     # See if we need to remove it from them
        #     for i in bong_role.members + [current_bong_member]:
        #         if i is not None and i.id != new_bong_member.id:
        #             await i.remove_roles(bong_role)
        #             self.logger.info(f"Removed bong role ({bong_role.id}) from member (G{guild.id}/U{i.id})")

        #     # Add the role to the new person
        #     await new_bong_member.add_roles(bong_role)
        #     self.logger.info(f"Added bong role ({bong_role.id}) to member (G{guild.id}/U{new_bong_member.id})")

        # # Oh well
        # except discord.Forbidden:
        #     return self.logger.info(f"Can't manage roles in guild {guild.id}")
        # except discord.NotFound:
        #     return self.logger.info(f"Role G{guild.id}/R{role_id} doesn't exist")


def setup(bot: vbu.Bot):
    bot.startup_method = bot.loop.create_task(bot.startup())
    x = BongHandler(bot)
    bot.add_cog(x)
