CREATE TABLE guild_settings(
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(30),
    bong_channel_id BIGINT,
    bong_role_id BIGINT,
    bong_emoji VARCHAR(50)
);


CREATE TABLE user_settings(
    user_id BIGINT PRIMARY KEY
);


CREATE TABLE role_list(
    guild_id BIGINT,
    role_id BIGINT,
    key VARCHAR(50),
    value VARCHAR(50),
    PRIMARY KEY (guild_id, role_id, key)
);


CREATE TABLE bong_log(
    guild_id BIGINT,
    user_id BIGINT,
    timestamp TIMESTAMP
    message_timestamp TIMESTAMP
);
