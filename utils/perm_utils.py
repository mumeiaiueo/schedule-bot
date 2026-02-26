# utils/perm_utils.py
import discord

async def is_manager(interaction: discord.Interaction, dm) -> bool:
    """
    ✅ True なら「管理コマンド実行OK」
    - サーバー管理者 ならOK
    - それ以外は guild_settings.manager_role_id を持っていればOK
    """
    user = interaction.user
    if not isinstance(user, discord.Member):
        return False

    # 管理者は常にOK
    if user.guild_permissions.administrator:
        return True

    # 管理ロールが未設定ならNG
    role_id = await dm.get_manager_role_id(str(interaction.guild_id))
    if not role_id:
        return False

    return any(r.id == int(role_id) for r in user.roles)