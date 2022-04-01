import typing

import discord
from discord.ext import commands, vbu


class BigBen(vbu.Cog):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta()
    )
    @commands.defer()
    @commands.has_permissions(manage_guild=True)
    async def testbong(self, ctx: vbu.SlashContext):
        """
        Send a test bong.
        """

        self.bot.dispatch("bong", ctx.interaction.guild_id)
        return await ctx.send("Dispatched test bong.")

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user whose bong count you want to check.",
                    required=False,
                    type=discord.ApplicationCommandOptionType.user,
                )
            ]
        )
    )
    @commands.defer()
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def bongcount(self, ctx: vbu.SlashContext, user: typing.Optional[discord.Member] = None):
        """
        Counts how many times a user has gotten the first bong reaction.
        """

        # Work out who we're running the command on
        user = user or ctx.author  # type: ignore
        assert user  # Make sure it's actually set

        # Get the data we need
        async with self.bot.database() as db:
            rows = await db("SELECT * FROM bong_log WHERE guild_id=$1 AND user_id=$2", ctx.interaction.guild_id, user.id)

        # Format and send their data
        if rows:
            average = sum([(i['timestamp'] - i['message_timestamp']).total_seconds() for i in rows]) / len(rows)
            return await ctx.send(
                f"{user.mention} has gotten the first bong reaction {len(rows)} times, "
                f"averaging a {average:,.2f}s reaction time."
            )
        return await ctx.send(f"{user.mention} has gotten the first bong reaction 0 times :c")

    @commands.command(
        aliases=['lb'],
        application_command_meta=commands.ApplicationCommandMeta(),
    )
    @commands.defer()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.guild_only()
    async def leaderboard(self, ctx: vbu.SlashContext):
        """
        Gives you the bong leaderboard.
        """

        async with self.bot.database() as db:
            rows = await db(
                """SELECT user_id, count(user_id) FROM bong_log WHERE guild_id=$1 GROUP BY user_id
                ORDER BY count(user_id) DESC, user_id DESC""",
                ctx.interaction.guild_id,
            )
        if not rows:
            return await ctx.send("Nobody has reacted to the bong message yet on your server :<")
        lines = [f"{index}. <@{row['user_id']}> ({row['count']} bongs)" for index, row in enumerate(rows, start=1)]
        await vbu.Paginator(lines, per_page=10).start(ctx)


    # @commands.command(enabled=False)
    # @commands.bot_has_permissions(send_messages=True, attach_files=True, embed_links=True)
    # @commands.guild_only()
    # async def bongdist(self, ctx: vbu.SlashContext, user: discord.Member = None):
    #     """
    #     Gives you the bong leaderboard.
    #     """

    #     user = user or ctx.author
    #     async with self.bot.database() as db:
    #         rows = await db("SELECT timestamp - message_timestamp AS reaction_time FROM bong_log WHERE user_id=$1 AND guild_id=$2", user.id, ctx.interaction.guild_id)
    #     if not rows:
    #         return await ctx.send(f"{user.mention} has reacted to the bong message yet on your server.")

    #     # Build our output graph
    #     fig = plt.figure()
    #     ax = fig.subplots()
    #     bplot = ax.boxplot([i['reaction_time'].total_seconds() for i in rows], patch_artist=True)
    #     ax.axis([0, 2, 0, 10])

    #     for i in bplot['boxes']:
    #         i.set_facecolor('lightblue')

    #     # Fix axies
    #     ax.grid(True)

    #     # Tighten border
    #     fig.tight_layout()

    #     # Output to user baybeeee
    #     fig.savefig('activity.png', bbox_inches='tight', pad_inches=0)
    #     with vbu.Embed() as embed:
    #         # Build the embed
    #         embed = discord.Embed(title=f"{ctx.author.name}'s average reaction time")
    #         embed.set_image(url="attachment://activity.png")
    #     await ctx.send(embed=embed, file=discord.File("activity.png"))


def setup(bot: vbu.Bot):
    x = BigBen(bot)
    bot.add_cog(x)
