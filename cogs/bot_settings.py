import voxelbotutils as vbu
import discord
from discord.ext import commands


async def bong_channel_storage_whatever(menu, channel: discord.TextChannel):
    await utils.SettingsMenuOption.get_set_guild_settings_callback('guild_settings', 'bong_channel_id')(menu, channel)
    if channel is None:
        return
    try:
        webhook = await channel.create_webhook(name="Big Ben")
    except discord.HTTPException:
        return
    async with menu.context.bot.database() as db:
        await db(
            """INSERT INTO guild_settings (guild_id, bong_channel_webhook)
            VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET bong_channel_webhook=$2""",
            menu.context.guild.id, webhook.url
        )
    menu.context.bot.guild_settings[menu.context.guild.id]["bong_channel_webhook"] = webhook.url


class BotSettings(vbu.Cog):

    @vbu.group()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(send_messages=True, embed_links=True, add_reactions=True)
    @commands.guild_only()
    async def setup(self, ctx: vbu.Context):
        """
        Run the bot setup.
        """

        # Make sure it's only run as its own command, not a parent
        if ctx.invoked_subcommand is not None:
            return

        # Create settings menu
        menu = vbu.SettingsMenu()
        settings_mention = vbu.SettingsMenuOption.get_guild_settings_mention
        menu.add_multiple_options(
            vbu.SettingsMenuOption(
                ctx=ctx,
                display=lambda c: "Set bong channel (currently {0})".format(settings_mention(c, 'bong_channel_id')),
                converter_args=(
                    vbu.SettingsMenuConverter(
                        prompt="Where do you want all the bong messages to go to?",
                        asking_for="bong channel",
                        converter=commands.TextChannelConverter,
                    ),
                ),
                callback=bong_channel_storage_whatever,
            ),
            vbu.SettingsMenuOption(
                ctx=ctx,
                display=lambda c: "Set 'first bong reaction' role (currently {0})".format(settings_mention(c, 'bong_role_id')),
                converter_args=(
                    vbu.SettingsMenuConverter(
                        prompt="Which role should the first reaction to the bong message get?",
                        asking_for="bong channel",
                        converter=commands.RoleConverter,
                    ),
                ),
                callback=vbu.SettingsMenuOption.get_set_guild_settings_callback('guild_settings', 'bong_role_id'),
            ),
            vbu.SettingsMenuOption(
                ctx=ctx,
                display=lambda c: "Set bong reaction emoji (currently {0})".format(c.bot.guild_settings[c.guild.id]['bong_emoji']),
                converter_args=(
                    vbu.SettingsMenuConverter(
                        prompt="What should emoji should be added to each bong message?",
                        asking_for="bong emoji",
                        converter=str,
                    ),
                ),
                callback=vbu.SettingsMenuOption.get_set_guild_settings_callback('guild_settings', 'bong_emoji'),
            ),
        )
        try:
            await menu.start(ctx)
            await ctx.send("Done setting up!")
        except vbu.errors.InvokedMetaCommand:
            pass


def setup(bot: vbu.Bot):
    x = BotSettings(bot)
    bot.add_cog(x)
