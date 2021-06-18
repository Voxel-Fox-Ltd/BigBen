CREATE TABLE IF NOT EXISTS guild_settings(
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(30),
    bong_channel_id BIGINT,
    bong_channel_webhook VARCHAR(150),
    bong_role_id BIGINT,
    bong_emoji VARCHAR(50)
);


CREATE TABLE IF NOT EXISTS user_settings(
    user_id BIGINT PRIMARY KEY
);


CREATE TABLE IF NOT EXISTS role_list(
    guild_id BIGINT,
    role_id BIGINT,
    key VARCHAR(50),
    value VARCHAR(50),
    PRIMARY KEY (guild_id, role_id, key)
);


CREATE TABLE IF NOT EXISTS channel_list(
    guild_id BIGINT,
    channel_id BIGINT,
    key VARCHAR(50),
    value VARCHAR(50),
    PRIMARY KEY (guild_id, channel_id, key)
);


CREATE TABLE IF NOT EXISTS bong_log(
    guild_id BIGINT,
    user_id BIGINT,
    timestamp TIMESTAMP,
    message_timestamp TIMESTAMP
);


CREATE TABLE IF NOT EXISTS bong_override_text(
    guild_id BIGINT,
    date DATE,
    text VARCHAR(200),
    PRIMARY KEY (guild_id, date)
);
