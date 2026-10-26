import asyncio
import json
import logging
import os

import discord
from discord import app_commands


GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])
CATEGORY_ID = int(os.environ["TICKET_CATEGORY_ID"])
SUPPORT_ROLE_ID = int(os.environ["SUPPORT_ROLE_ID"])
GUILD = discord.Object(id=GUILD_ID)
PREFIX = "betclic-ticket:"
LOCK = asyncio.Lock()
LOG = logging.getLogger("tickets")


def ticket_data(channel):
    if not isinstance(channel, discord.TextChannel):
        return None
    if channel.guild.id != GUILD_ID or channel.category_id != CATEGORY_ID:
        return None
    if not (channel.topic or "").startswith(PREFIX):
        return None
    try:
        data = json.loads(channel.topic[len(PREFIX):])
        if (type(data["owner"]) is int and data["owner"] > 0
                and type(data["closed"]) is bool
                and type(data["claimed"]) is int):
            return data
    except (ValueError, KeyError, TypeError):
        pass
    return None


def is_staff(member):
    return (isinstance(member, discord.Member)
            and member.guild.id == GUILD_ID
            and (member.guild_permissions.administrator
                 or any(r.id == SUPPORT_ROLE_ID for r in member.roles)))


async def reply(interaction, text):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


async def report_error(interaction, error):
    LOG.error("Falha na operação do ticket", exc_info=(type(error), error, error.__traceback__))
    await reply(interaction, "Não foi possível concluir o pedido. Tenta novamente ou contacta a equipa.")


class SafeView(discord.ui.View):
    async def on_error(self, interaction, error, item):
        await report_error(interaction, error)


def ticket_text(data):
    state = "Fechado" if data["closed"] else "Aberto"
    agent = f'<@{data["claimed"]}>' if data["claimed"] else "Por atribuir"
    return (
        f'<@{data["owner"]}> O teu ticket foi criado.\n'
        "Fornece-nos qualquer informação adicional que consideres útil "
        "para nos ajudar a responder mais rapidamente.\n\n"
        f"**Estado:** {state}\n**Responsável:** {agent}"
    )


async def perform(interaction, action):
    if not is_staff(interaction.user):
        return await reply(interaction, "Só a equipa pode gerir os tickets.")
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with LOCK:
        channel = await interaction.client.fetch_channel(interaction.channel_id)
        data = ticket_data(channel)
        if data is None:
            return await reply(interaction, "Este canal não é um ticket deste bot.")

        if action == "delete":
            if not data["closed"]:
                return await reply(interaction, "Fecha o ticket antes de o eliminar.")
            return await interaction.followup.send(
                "Eliminar este ticket e todas as mensagens? Esta ação é permanente.",
                view=DeleteConfirmation(interaction.user.id), ephemeral=True,
            )

        if action == "confirm_delete":
            if not data["closed"]:
                return await reply(interaction, "O ticket foi reaberto. Fecha-o antes de o eliminar.")
            await channel.delete(reason=f"Ticket eliminado por {interaction.user.id}")
            return await reply(interaction, "Ticket eliminado.")

        if action == "claim":
            if data["closed"]:
                return await reply(interaction, "Reabre o ticket antes de o assumir.")
            if data["claimed"] and data["claimed"] != interaction.user.id:
                return await reply(interaction, "Este ticket já foi assumido por outro membro da equipa.")
            data["claimed"] = interaction.user.id
        else:
            closed = action == "close"
            if data["closed"] == closed:
                return await reply(interaction, "O ticket já está nesse estado.")
            # Resolve the owner's member overwrite even after they leave the server.
            target = next((t for t in channel.overwrites if t.id == data["owner"]), None)
            if target is None:
                target = await channel.guild.fetch_member(data["owner"])
            overwrites = channel.overwrites
            member_permissions = channel.overwrites_for(target)
            member_permissions.update(
                view_channel=True, read_message_history=True,
                send_messages=not closed, add_reactions=not closed,
                send_messages_in_threads=False, create_public_threads=False,
                create_private_threads=False,
            )
            overwrites[target] = member_permissions
            data["closed"] = closed
            # Permissions and state are updated in the same Discord request.
            await channel.edit(overwrites=overwrites, topic=PREFIX + json.dumps(data))

        if action == "claim":
            await channel.edit(topic=PREFIX + json.dumps(data))
        await interaction.message.edit(content=ticket_text(data), view=TicketView(data["closed"]))
        await reply(interaction, {
            "claim": "Assumiste este ticket.",
            "close": "Ticket fechado. O membro pode consultar o histórico, mas não enviar mensagens.",
            "reopen": "Ticket reaberto.",
        }[action])


class DeleteConfirmation(SafeView):
    def __init__(self, requester):
        super().__init__(timeout=60)
        self.requester = requester

    @discord.ui.button(label="Sim, eliminar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        if interaction.user.id != self.requester:
            return await reply(interaction, "Esta confirmação pertence a outro utilizador.")
        await perform(interaction, "confirm_delete")
        self.stop()


class TicketView(SafeView):
    def __init__(self, closed=False):
        super().__init__(timeout=None)
        self.claim.disabled = closed
        self.close_ticket.disabled = closed
        self.reopen.disabled = not closed
        self.delete.disabled = not closed

    @discord.ui.button(label="Assumir", emoji="🎟️", style=discord.ButtonStyle.primary, custom_id="betclic:claim")
    async def claim(self, interaction, button):
        await perform(interaction, "claim")

    @discord.ui.button(label="Fechar", emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="betclic:close")
    async def close_ticket(self, interaction, button):
        await perform(interaction, "close")

    @discord.ui.button(label="Reabrir", emoji="🔓", style=discord.ButtonStyle.success, custom_id="betclic:reopen")
    async def reopen(self, interaction, button):
        await perform(interaction, "reopen")

    @discord.ui.button(label="Eliminar", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="betclic:delete")
    async def delete(self, interaction, button):
        await perform(interaction, "delete")


class ContactView(SafeView):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Contactar a equipa", emoji="📩", style=discord.ButtonStyle.danger, custom_id="betclic:open")
    async def open_ticket(self, interaction, button):
        if interaction.guild_id != GUILD_ID or not isinstance(interaction.user, discord.Member):
            return await reply(interaction, "Este botão só funciona no servidor configurado.")
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with LOCK:
            channels = await interaction.guild.fetch_channels()
            for channel in channels:
                data = ticket_data(channel)
                if data and data["owner"] == interaction.user.id:
                    return await reply(interaction, f"Já tens um ticket: {channel.mention}. Se estiver fechado, pede à equipa para o reabrir.")
            category = discord.utils.get(channels, id=CATEGORY_ID)
            role = interaction.guild.get_role(SUPPORT_ROLE_ID)
            if not isinstance(category, discord.CategoryChannel) or role is None or role.is_default():
                return await reply(interaction, "A configuração dos tickets precisa de ser revista pela equipa.")
            access = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                attach_files=True, embed_links=True,
                create_public_threads=False, create_private_threads=False,
                send_messages_in_threads=False,
            )
            data = {"owner": interaction.user.id, "closed": False, "claimed": 0}
            channel = await interaction.guild.create_text_channel(
                name=f"ticket-{interaction.user.id}", category=category,
                topic=PREFIX + json.dumps(data),
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    interaction.guild.me: access,
                    role: access,
                    interaction.user: access,
                },
                reason=f"Ticket de {interaction.user.id}",
            )
            try:
                await channel.send(ticket_text(data), view=TicketView())
            except discord.HTTPException:
                # Avoid leaving a ticket with no management buttons on initial failure.
                await channel.delete(reason="Falha ao criar a mensagem inicial")
                raise
            await reply(interaction, f"O teu ticket foi criado: {channel.mention}")


class TicketBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(ContactView())
        self.add_view(TicketView())
        await self.tree.sync(guild=GUILD)

    async def on_ready(self):
        guild = self.get_guild(GUILD_ID)
        if guild is None:
            raise RuntimeError("O bot não está no DISCORD_GUILD_ID configurado.")
        LOG.info("Bot ligado: %s", self.user)


bot = TicketBot()


@bot.tree.command(name="painel", description="Publicar o painel de contacto neste canal.", guild=GUILD)
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def panel(interaction: discord.Interaction):
    if (interaction.guild_id != GUILD_ID or not isinstance(interaction.user, discord.Member)
            or not interaction.user.guild_permissions.administrator):
        return await reply(interaction, "Só um administrador pode publicar o painel.")
    if not isinstance(interaction.channel, discord.TextChannel):
        return await reply(interaction, "Usa este comando num canal de texto.")
    await interaction.response.defer(ephemeral=True, thinking=True)
    embed = discord.Embed(
        title="Contactar a equipa",
        description="Clica no botão abaixo para criar um ticket.",
        colour=0xED0000,
    )
    await interaction.channel.send(embed=embed, view=ContactView())
    await reply(interaction, "Painel publicado.")


@bot.tree.error
async def command_error(interaction, error):
    await report_error(interaction, error)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot.run(os.environ["DISCORD_TOKEN"])
