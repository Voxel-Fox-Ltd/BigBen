import asyncio
from datetime import datetime as dt
import re
import collections

import discord
from discord.ext import commands, tasks
import voxelbotutils as vbu
from matplotlib import pyplot as plt


class BigBen(vbu.Cog):

    EMOJI_REGEX = re.compile(r"<a?:(?P<name>.+?):(?P<id>\d+?)>")
    DEFAULT_BONG_TEXT = "Bong"
    BONG_TEXT = {
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
        self.bing_bong.start()
        self.bong_messages = set()
        self.added_bong_reactions = set()
        self.bong_message_locks = collections.defaultdict(asyncio.Lock)

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

    async def send_guild_bong_message(self, text: str, now: dt, guild_id: int, settings: dict, channels_to_delete: list):
        """
        An async function that does the actual sending of the bong message.
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
            url = webhook_url + "?wait=1"
            payload.update({
                "wait": True,
                "username": self.bot.user.name,
                "avatar_url": avatar_url,
            })

            # Set up our emoji to be added
            emoji = settings['bong_emoji']
            if emoji is not None:
                if emoji.startswith("<"):
                    match = self.EMOJI_REGEX.search(emoji)
                    found = match.group("id")
                    if not self.bot.get_emoji(int(found)):
                        self.logger.info(f"Add reaction cancelled - emoji with ID {found} not found")
                        emoji = None

            # See if we should get some other text
            override_text = settings.get('override_text', {}).get(f"{now.month}-{now.day}")
            payload['content'] = override_text or text

            # Set up the components to be added
            if emoji:
                payload['components'] = vbu.MessageComponents(vbu.ActionRow(vbu.Button(
                    custom_id="BONG MESSAGE BUTTON",
                    emoji=emoji,
                    style=vbu.ButtonStyle.SECONDARY,
                ))).to_dict()

            # Send message
            try:
                site = await self.bot.session.post(url, json=payload)
                message_payload = await site.json()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
                self.logger.info(f"Send failed - {e} (G{guild_id}/C{channel_id})")
                return

            # Cache message
            self.bong_messages.add(int(message_payload['id']))
            self.logger.info(f"Sent bong message to channel (G{guild_id}/C{channel_id}/M{message_payload['id']})")

        except Exception as e:
            self.logger.info(f"Failed sending message to guild (G{guild_id}) - {e}")

    @vbu.Cog.listener("on_bong")
    async def do_bong(self, bong_guild_id: int = None):
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
        channels_to_delete = []
        if bong_guild_id is None:
            self.bong_messages.clear()  # Clear for the reacted to bong first role
            self.added_bong_reactions.clear()  # Clear for the adding "bong" to people's messages

        # Set up what we need to wait for
        tasks_to_gather = []

        # Let's see our cached guilds
        for guild_id, settings in self.bot.guild_settings.copy().items():

            # See if we give a shit about this guild
            if bong_guild_id is not None and bong_guild_id != guild_id:
                continue

            # See if we want to handle this guild, or if that's up to another process
            if (guild_id >> 22) % self.bot.shard_count not in self.bot.shard_ids:
                continue

            # See if we're still in that guild
            if self.bot.get_guild(guild_id) is None:
                continue

            # See if they have a webhook
            if settings.get("bong_channel_webhook"):
                tasks_to_gather.append(self.send_guild_bong_message(
                    text, now, guild_id, settings, channels_to_delete,
                ))

        # Gather all of our data
        await asyncio.gather(*tasks_to_gather)

        # Sick we're done
        self.logger.info("Done sending bong messages")

        # Delete channels that we should no longer care about
        async with self.bot.database() as db:
            await db("UPDATE guild_settings SET bong_channel_id=NULL WHERE guild_id=ANY($1::BIGINT[])", channels_to_delete)
        for guild_id in channels_to_delete:
            self.bot.guild_settings[guild_id]['bong_channel_id'] = None

    @vbu.command(hidden=True)
    @commands.has_permissions(manage_guild=True)
    async def testbong(self, ctx: vbu.Context):
        """
        Send a test bong.
        """

        self.bot.dispatch("bong", ctx.guild.id)
        return await ctx.send("Dispatched test bong.")

    @bing_bong.before_loop
    async def before_bing_bong(self):
        await self.bot.wait_until_ready()

    async def disable_components(self, payload: vbu.ComponentInteractionPayload):
        """
        Disable the components on a message.
        """

        edit_url = self.bot.guild_settings[payload.guild.id]['bong_channel_webhook'].rstrip("/") + f"/messages/{payload.message.id}"
        self.logger.info(payload.message.components.to_dict())
        self.logger.info(payload.message.components.disable_components().to_dict())
        site = await self.bot.session.patch(
            edit_url,
            json={
                'components': payload.message.components.disable_components().to_dict(),
            },
        )
        output = await site.text()
        self.logger.info(f"Tried to disable components on message {payload.message.id} - {output}")

    @vbu.Cog.listener()
    async def on_component_interaction(self, payload: vbu.ComponentInteractionPayload):
        """
        Waits for the bong button to be pressed
        """

        # See if it's a bong button
        if payload.component.custom_id != "BONG MESSAGE BUTTON":
            return
        async with self.bong_message_locks[payload.message.id]:
            await self.handle_bong_component(payload)

    async def handle_bong_component(self, payload: vbu.ComponentInteractionPayload):
        """
        Handle a bong button being pressed
        """

        # Check that it wasn't already reacted to
        if payload.message.id not in self.bong_messages:
            self.bot.loop.create_task(self.disable_components(payload))
            return await payload.send("You weren't the first person to click the button :c", wait=False, ephemeral=True)
        await payload.send("You were the first to react! :D", wait=False, ephemeral=True)
        self.bot.loop.create_task(self.disable_components(payload))

        # Check they gave the right reaction
        guild = self.bot.get_guild(payload.guild.id) or await self.bot.fetch_guild(payload.guild.id)

        # Database handle
        self.logger.info(f"Guild {guild.id} with user {payload.user.id} in {dt.utcnow() - discord.Object(payload.message.id).created_at}")
        self.bong_messages.discard(payload.message.id)
        async with self.bot.database() as db:
            current_bong_member_rows = await db("SELECT * FROM bong_log WHERE guild_id=$1 ORDER BY timestamp DESC LIMIT 1", guild.id)
            await db(
                """INSERT INTO bong_log (guild_id, user_id, timestamp, message_timestamp) VALUES ($1, $2, $3, $4)""",
                guild.id, payload.user.id, dt.utcnow(), discord.Object(payload.message.id).created_at,
            )

        # Check they have a role set up
        role_id = self.bot.guild_settings[guild.id]['bong_role_id']
        if role_id is None:
            return

        # Get the bong role
        try:
            bong_role = guild.get_role(role_id) or [i for i in await guild.fetch_roles() if i.id == role_id][0]
        except (IndexError, discord.HTTPException):
            bong_role = None
        if bong_role is None:
            return self.logger.info(f"Bong role doesn't exist (G{guild.id})")

        # See who currently has it
        if current_bong_member_rows:
            current_bong_member_id = current_bong_member_rows[0]['user_id']
            try:
                current_bong_member = guild.get_member(current_bong_member_id) or await guild.fetch_member(current_bong_member_id)
            except discord.HTTPException:
                current_bong_member = None
        else:
            current_bong_member = None

        # See who we want to give it to
        new_bong_member = guild.get_member(payload.user.id) or await guild.fetch_member(payload.user.id)

        # See if we can remove the role from the people who have it
        try:

            # See if we need to remove it from them
            if current_bong_member is not None and current_bong_member.id != new_bong_member.id:
                await current_bong_member.remove_roles(bong_role)
                self.logger.info(f"Removed bong role ({bong_role.id}) from member (G{guild.id}/U{current_bong_member.id})")

            # Add the role to them
            await new_bong_member.add_roles(bong_role)
            self.logger.info(f"Added bong role ({bong_role.id}) to member (G{guild.id}/U{new_bong_member.id})")

        # Oh well
        except discord.Forbidden:
            return self.logger.info(f"Can't manage roles in guild {guild.id}")

    @vbu.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Listens for people saying 'bong' and reacts to it BUT only once an hour.
        """

        # Don't respond to bots
        if message.author.bot:
            return

        # Don't respond in DMs
        if isinstance(message.channel, discord.DMChannel):
            return

        # Don't respond if they already got a reaction
        if (message.guild.id, message.author.id) in self.added_bong_reactions:
            return

        # Check valid string
        valid_strings = [self.DEFAULT_BONG_TEXT.lower(), 'early ' + self.DEFAULT_BONG_TEXT.lower(), 'late ' + self.DEFAULT_BONG_TEXT.lower()]
        if message.content.lower().strip(' .,;?!') not in valid_strings:
            return

        # Add reaction
        try:
            if dt.utcnow().minute > 45:
                await message.add_reaction("<:EarlyBong:699703641560449065>")
            elif dt.utcnow().minute > 15:
                await message.add_reaction("<:LateBong:699701882255311031>")
            else:
                await message.add_reaction("<:Bong:699705094253576222>")
            self.added_bong_reactions.add((message.guild.id, message.author.id))
        except (discord.Forbidden, discord.NotFound) as e:
            self.logger.info(f"Couldn't react to message {message.id} - {e}")
        except discord.HTTPException as e:
            self.logger.critical(f"Couldn't add reaction - {e}")

    @vbu.command()
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def bongcount(self, ctx: vbu.Context, user: discord.Member = None):
        """
        Counts how many times a user has gotten the first bong reaction.
        """

        user = user or ctx.author
        async with self.bot.database() as db:
            rows = await db("SELECT * FROM bong_log WHERE guild_id=$1 AND user_id=$2", ctx.guild.id, user.id)
        if rows:
            average = sum([(i['timestamp'] - i['message_timestamp']).total_seconds() for i in rows]) / len(rows)
            return await ctx.send(f"{user.mention} has gotten the first bong reaction {len(rows)} times, averaging a {average:,.2f}s reaction time.")
        return await ctx.send(f"{user.mention} has gotten the first bong reaction 0 times :c")

    @vbu.command(aliases=['lb'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.guild_only()
    async def leaderboard(self, ctx: vbu.Context):
        """
        Gives you the bong leaderboard.
        """

        async with self.bot.database() as db:
            rows = await db(
                """SELECT user_id, count(user_id) FROM bong_log WHERE guild_id=$1 GROUP BY user_id
                ORDER BY count(user_id) DESC, user_id DESC""",
                ctx.guild.id,
            )
        if not rows:
            return await ctx.send("Nobody has reacted to the bong message yet on your server :<")
        lines = [f"{index}. <@{row['user_id']}> ({row['count']} bongs)" for index, row in enumerate(rows, start=1)]
        await vbu.Paginator(lines, per_page=10).start(ctx)

    @vbu.command(enabled=False)
    @commands.bot_has_permissions(send_messages=True, attach_files=True, embed_links=True)
    @commands.guild_only()
    async def bongdist(self, ctx: vbu.Context, user: discord.Member = None):
        """
        Gives you the bong leaderboard.
        """

        user = user or ctx.author
        async with self.bot.database() as db:
            rows = await db("SELECT timestamp - message_timestamp AS reaction_time FROM bong_log WHERE user_id=$1 AND guild_id=$2", user.id, ctx.guild.id)
        if not rows:
            return await ctx.send(f"{user.mention} has reacted to the bong message yet on your server.")

        # Build our output graph
        fig = plt.figure()
        ax = fig.subplots()
        bplot = ax.boxplot([i['reaction_time'].total_seconds() for i in rows], patch_artist=True)
        ax.axis([0, 2, 0, 10])

        for i in bplot['boxes']:
            i.set_facecolor('lightblue')

        # Fix axies
        ax.grid(True)

        # Tighten border
        fig.tight_layout()

        # Output to user baybeeee
        fig.savefig('activity.png', bbox_inches='tight', pad_inches=0)
        with vbu.Embed() as embed:
            # Build the embed
            embed = discord.Embed(title=f"{ctx.author.name}'s average reaction time")
            embed.set_image(url="attachment://activity.png")
        await ctx.send(embed=embed, file=discord.File("activity.png"))


def setup(bot: vbu.Bot):
    x = BigBen(bot)
    bot.add_cog(x)
