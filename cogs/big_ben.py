from datetime import datetime as dt

import discord
from discord.ext import commands
from discord.ext import tasks
from discord.ext import menus
from matplotlib import pyplot as plt

from cogs import utils


class SimpleMenuSource(menus.ListPageSource):

    def format_page(self, menu, entries):
        with utils.Embed(use_random_colour=True) as embed:
            embed.description = '\n'.join(entries)
        return embed


class BigBen(utils.Cog):

    DEFAULT_BONG_TEXT = "Bong"
    BONG_TEXT = {
        (1, 1): "{0.year} Bong",
        (14, 2): "Valentine's Bong",
        (1, 4): "Bing",
        (22, 4): "Earth Bong",
        (2, 7): "Midway Bong",
        (6, 9): "Birthday Bong",
        (31, 10): "Halloween Bong",
        (25, 12): "Christmas Bong",

        (12, 4, 2020): "Easter Bong",
        (4, 4, 2021): "Easter Bong",
        (17, 4, 2022): "Easter Bong",
        (9, 4, 2023): "Easter Bong",
        (31, 3, 2024): "Easter Bong",
    }  # (DD, MM, YYYY?): Output

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)
        self.last_posted_hour: int = None
        self.bing_bong.start()
        self.bong_messages = []
        self.other_people_bong_this_hour = []

    def cog_unload(self):
        self.bing_bong.cancel()

    @tasks.loop(seconds=1)
    async def bing_bong(self):
        """Do the bong"""

        # See if it should post
        now = dt.utcnow()
        if now.hour != self.last_posted_hour and now.minute == 0:
            self.last_posted_hour = now.hour
        else:
            return
        self.bot.dispatch("bong")

    @utils.Cog.listener("on_bong")
    async def do_bong(self, bong_guild_id:int=None):
        """Dispatch the bong message"""

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
        if bong_guild_id is None:
            self.bong_messages.clear()
            self.other_people_bong_this_hour.clear()
        for guild_id, settings in self.bot.guild_settings.copy().items():

            # See if we give a shit about this guild
            if bong_guild_id is not None and bong_guild_id != guild_id:
                continue

            # Try for the guild
            try:

                # Grab channel
                channel = self.bot.get_channel(settings['bong_channel_id'])
                if channel is None:
                    self.logger.info(f"Send failed - missing channel (G{guild_id}/C{settings['bong_channel_id']})")
                    continue

                # See if we should get some other text
                override_text = settings['override_text'].get(f"{now.month}-{now.day}")

                # Send message
                try:
                    message = await channel.send(override_text or text)
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
                    self.logger.info(f"Send failed - {e} (G{guild_id}/C{settings['bong_channel_id']})")
                    continue

                # Cache message
                self.bong_messages.append(message.id)
                self.logger.info(f"Sent bong message to channel (G{message.guild.id}/C{message.channel.id}/M{message.id})")

                # Add emoji
                emoji = settings['bong_emoji']
                if emoji is not None:
                    try:
                        await message.add_reaction(emoji)
                        self.logger.info(f"Added reaction to bong message (G{message.guild.id}/C{message.channel.id}/M{message.id})")
                    except Exception:
                        self.logger.info(f"Couldn't add reaction to bong message (G{message.guild.id}/C{message.channel.id}/M{message.id})")

            except Exception as e:
                self.logger.info(f"Failed sending message to guild (G{message.guild.id}) - {e}")
        self.logger.info("Done sending bong messages")

    @utils.Cog.listener("on_bong")
    async def update_profile_picture(self, bong_guild_id:int=None):
        """Update the bot's profile picture"""

        if bong_guild_id is not None:
            return

        with open(f"config/images/{dt.utcnow().hour % 12}.png", "rb") as a:
            data = a.read()
        self.logger.info("Updating bot user profile picture")
        await self.bot.user.edit(avatar=data)
        self.logger.info("Updated bot user profile picture successfully")

    @commands.command(cls=utils.Command, hidden=True)
    @commands.has_permissions(manage_guild=True)
    async def testbong(self, ctx:utils.Context):
        """Send a test bong"""

        self.bot.dispatch("bong", ctx.guild.id)
        return await ctx.send("Dispatched test bong.")

    @bing_bong.before_loop
    async def before_bing_bong(self):
        await self.bot.wait_until_ready()

    @utils.Cog.listener()
    async def on_reaction_add(self, reaction:discord.Reaction, user:discord.User):
        """Waits for a reaction add"""

        # Check it's on a big ben message
        if reaction.message.id not in self.bong_messages:
            return

        # Check they gave the right reaction
        guild = reaction.message.guild
        emoji = self.bot.guild_settings[guild.id]['bong_emoji']
        if emoji and str(reaction.emoji) != emoji:
            return

        # Check it's not a bot
        if user.bot:
            return

        # Database handle
        self.logger.info(f"Guild {reaction.message.guild.id} with user {user.id} in {dt.utcnow() - reaction.message.created_at}")
        self.bong_messages.remove(reaction.message.id)
        async with self.bot.database() as db:
            await db(
                "INSERT INTO bong_log (guild_id, user_id, timestamp, message_timestamp) VALUES ($1, $2, $3, $4)",
                guild.id, user.id, dt.utcnow(), reaction.message.created_at,
            )

        # Check they have a role set up
        role_id = self.bot.guild_settings[guild.id]['bong_role_id']
        if role_id is None:
            return

        # Role handle
        bong_role = guild.get_role(role_id)
        if bong_role is None:
            return self.logger.info(f"Bong role doesn't exist (G{guild.id})")
        try:
            for member in bong_role.members:
                if user.id != member.id:
                    await member.remove_roles(bong_role)
                    self.logger.info(f"Removed bong role ({bong_role.id}) from member (G{guild.id}/U{member.id})")
            await guild.get_member(user.id).add_roles(bong_role)
            self.logger.info(f"Added bong role ({bong_role.id}) to member (G{guild.id}/U{member.id})")
        except discord.Forbidden:
            return self.logger.info(f"Can't manage roles in guild {guild.id}")

    @utils.Cog.listener()
    async def on_message(self, message:discord.Message):
        """Listens for people saying 'bong' and reacts to it BUT only once an hour"""

        # Don't respond to bots
        if message.author.bot:
            return

        # Don't respond in DMs
        if isinstance(message.channel, discord.DMChannel):
            return

        # Don't respond if they already got a reaction
        if (message.guild.id, message.author.id) in self.other_people_bong_this_hour:
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
            self.other_people_bong_this_hour.append((message.guild.id, message.author.id))
        except (discord.Forbidden, discord.NotFound) as e:
            self.logger.info(f"Couldn't react to message {message.id} - {e}")
        except discord.HTTPException as e:
            self.logger.critical(f"Couldn't add reaction - {e}")

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def bongcount(self, ctx, user:discord.Member=None):
        """Counts how many times a user has gotten the first bong reaction"""

        user = user or ctx.author
        async with self.bot.database() as db:
            rows = await db("SELECT * FROM bong_log WHERE guild_id=$1 AND user_id=$2", ctx.guild.id, user.id)
        if rows:
            average = sum([(i['timestamp'] - i['message_timestamp']).total_seconds() for i in rows]) / len(rows)
            return await ctx.send(f"{user.mention} has gotten the first bong reaction {len(rows)} times, averaging a {average:,.2f}s reaction time.")
        return await ctx.send(f"{user.mention} has gotten the first bong reaction 0 times :c")

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.guild_only()
    async def leaderboard(self, ctx):
        """Gives you the bong leaderboard"""

        async with self.bot.database() as db:
            rows = await db("SELECT user_id, count(user_id) FROM bong_log WHERE guild_id=$1 GROUP BY user_id ORDER BY count(user_id) DESC, user_id DESC", ctx.guild.id)
        if not rows:
            return await ctx.send("Nobody has reacted to the bong message yet on your server.")
        lines = [f"{index}. {ctx.guild.get_member(row['user_id']).mention} ({row['count']} bongs)" for index, row in enumerate(rows, start=1) if ctx.guild.get_member(row['user_id'])]
        source = SimpleMenuSource(lines, per_page=10)
        menu = menus.MenuPages(source=source)
        await menu.start(ctx)

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True, attach_files=True, embed_links=True)
    @commands.guild_only()
    async def bongdist(self, ctx:utils.Context, user:discord.Member=None):
        """Gives you the bong leaderboard"""

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
        # ax.axis('off')
        ax.grid(True)

        # Tighten border
        fig.tight_layout()

        # Output to user baybeeee
        fig.savefig('activity.png', bbox_inches='tight', pad_inches=0)
        with utils.Embed() as embed:
            # Build the embed   
            embed = discord.Embed(title= f"{ctx.author.name}'s average reaction time")
            embed.set_image(url="attachment://activity.png")
        await ctx.send(embed=embed, file=discord.File("activity.png"))


def setup(bot:utils.Bot):
    x = BigBen(bot)
    bot.add_cog(x)
