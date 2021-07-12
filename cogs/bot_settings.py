import voxelbotutils as vbu
import discord


async def bong_channel_storage_whatever(ctx, data):
    channel = data[0]
    await vbu.menus.Menu.callbacks.set_table_column(vbu.menus.DataLocation.GUILD, "guild_settings", "bong_channel_id")(ctx, (channel,))
    ctx.bot.guild_settings[ctx.guild.id]["bong_channel_id"] = channel.id if channel is not None else channel
    if channel is None:
        return
    try:
        webhook = await channel.create_webhook(name="Big Ben")
    except discord.HTTPException:
        return
    async with ctx.bot.database() as db:
        await db(
            """INSERT INTO guild_settings (guild_id, bong_channel_webhook)
            VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET bong_channel_webhook=$2""",
            ctx.guild.id, webhook.url,
        )
    ctx.bot.guild_settings[ctx.guild.id]["bong_channel_webhook"] = webhook.url


settings_menu = vbu.menus.Menu(
    vbu.menus.Option(
        display=lambda ctx: f"Set bong channel (currently {ctx.get_mentionable_channel(ctx.bot.guild_settings[ctx.guild.id]['bong_channel_id'])})",
        component_display="Set bong channel",
        converters=[
            vbu.menus.Converter(
                prompt="What channel do you want to set as your bong channel?",
                converter=discord.TextChannel,
            ),
        ],
        callback=bong_channel_storage_whatever,
        cache_callback=None,
    ),
    vbu.menus.Option(
        display=lambda ctx: f"Set bong role (currently {ctx.get_mentionable_role(ctx.bot.guild_settings[ctx.guild.id]['bong_role_id'])})",
        component_display="Set bong role",
        converters=[
            vbu.menus.Converter(
                prompt="What role should people get if they're the first to click the bong button?",
                converter=discord.Role,
            ),
        ],
        callback=vbu.menus.Menu.callbacks.set_table_column(vbu.menus.DataLocation.GUILD, "guild_settings", "bong_role_id"),
        cache_callback=vbu.menus.Menu.callbacks.set_cache_from_key(vbu.menus.DataLocation.GUILD, "bong_role_id"),
    ),
    vbu.menus.Option(
        display=lambda ctx: f"Set bong emoji (currently {ctx.bot.guild_settings[ctx.guild.id]['bong_emoji'] or 'null'})",
        component_display="Set bong emoji",
        converters=[
            vbu.menus.Converter(
                prompt="What should emoji should be added to each bong message?",
                converter=str,
            ),
        ],
        callback=vbu.menus.Menu.callbacks.set_table_column(vbu.menus.DataLocation.GUILD, "guild_settings", "bong_emoji"),
        cache_callback=vbu.menus.Menu.callbacks.set_cache_from_key(vbu.menus.DataLocation.GUILD, "bong_emoji"),
    ),
)


def setup(bot: vbu.Bot):
    settings_menu.create_cog(bot)
