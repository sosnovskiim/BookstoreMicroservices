CREATE TABLE identity.users (
    id serial primary key,
    email varchar(64) not null unique,
    password_hash varchar(255) not null,
    role varchar(16) not null default 'customer'
        check (role in ('customer', 'admin')),
    created_at timestamp not null default CURRENT_TIMESTAMP
);
