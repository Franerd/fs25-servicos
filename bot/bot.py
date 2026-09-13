import json
import os
import sqlite3
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "fs25_services.db"
SERVICES_PATH = ROOT / "data" / "services.json"
PACKAGES_PATH = ROOT / "data" / "packages.json"

load_dotenv(Path(__file__).with_name(".env"))
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
ORDERS_CHANNEL_ID = int(os.getenv("ORDERS_CHANNEL_ID", "0"))

with SERVICES_PATH.open(encoding="utf-8") as stream:
    SERVICES = {item["id"]: item for item in json.load(stream)}
with PACKAGES_PATH.open(encoding="utf-8") as stream:
    PACKAGES = {item["id"]: item for item in json.load(stream)}


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def setup_database():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            discord_id INTEGER PRIMARY KEY,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            farm TEXT NOT NULL,
            field_name TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            subtotal REAL NOT NULL,
            discount REAL NOT NULL,
            input_cost REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'aguardando_aprovacao',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES customers(discord_id)
        );
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(orders)")}
        if "input_cost" not in columns:
            db.execute("ALTER TABLE orders ADD COLUMN input_cost REAL NOT NULL DEFAULT 0")


def discount_rate(quantity, unit):
    if unit != "ha": return 0
    if quantity > 50: return .10
    if quantity > 25: return .08
    if quantity > 10: return .05
    return 0


def quote(item, quantity, input_cost=0):
    raw = item["price"] * quantity
    subtotal = max(raw, item.get("minimum", 0))
    rate = discount_rate(quantity, item["unit"])
    discount = subtotal * rate
    supplied_inputs = max(0, input_cost) * 1.10
    return subtotal, discount, subtotal - discount + supplied_inputs, rate, supplied_inputs


def money(value):
    return f"$ {value:,.0f}".replace(",", ".")


STATUS = {
    "aguardando_aprovacao": "🟡 Aguardando aprovação",
    "aprovada": "🟠 Aprovada / na fila",
    "em_andamento": "🔵 Em andamento",
    "concluida": "🟢 Concluída",
    "cancelada": "🔴 Cancelada",
}


class OrderView(discord.ui.View):
    def __init__(self, order_id):
        super().__init__(timeout=None)
        self.order_id = order_id

    async def change(self, interaction, status):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("Apenas a equipe pode alterar uma OS.", ephemeral=True)
            return
        with connect() as db:
            db.execute("UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, self.order_id))
        embed = interaction.message.embeds[0]
        embed.set_field_at(len(embed.fields)-1, name="Status", value=STATUS[status], inline=False)
        await interaction.response.edit_message(embed=embed, view=self if status not in ("concluida", "cancelada") else None)

    @discord.ui.button(label="Aprovar", emoji="✅", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, _): await self.change(interaction, "aprovada")

    @discord.ui.button(label="Iniciar", emoji="🚜", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, _): await self.change(interaction, "em_andamento")

    @discord.ui.button(label="Finalizar", emoji="🏁", style=discord.ButtonStyle.secondary)
    async def finish(self, interaction: discord.Interaction, _): await self.change(interaction, "concluida")

    @discord.ui.button(label="Cancelar", emoji="✖️", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, _): await self.change(interaction, "cancelada")


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    setup_database()
    print(f"Conectado como {bot.user}")
    if ORDERS_CHANNEL_ID:
        orders_channel = bot.get_channel(ORDERS_CHANNEL_ID)
        if orders_channel:
            permissions = orders_channel.permissions_for(orders_channel.guild.me)
            print(f"Canal de pedidos: #{orders_channel.name} | enviar={permissions.send_messages} | embeds={permissions.embed_links}")
        else:
            print("Canal de pedidos não está visível no cache do bot.")
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()


async def item_autocomplete(_, current: str):
    items = list(SERVICES.values()) + list(PACKAGES.values())
    return [app_commands.Choice(name=f"{x['name']} — {money(x['price'])}/{x['unit']}", value=x["id"])
            for x in items if current.lower() in x["name"].lower()][:25]


@bot.tree.command(name="orcamento", description="Calcula um orçamento de serviço agrícola")
@app_commands.describe(servico="Serviço ou pacote", quantidade="Hectares, horas ou viagens", insumos="Custo real dos insumos fornecidos pela empresa")
@app_commands.autocomplete(servico=item_autocomplete)
async def orcamento(interaction: discord.Interaction, servico: str, quantidade: app_commands.Range[float, 0.1, 10000.0], insumos: app_commands.Range[float, 0.0, 100000000.0] = 0):
    item = SERVICES.get(servico) or PACKAGES.get(servico)
    if not item:
        await interaction.response.send_message("Serviço não encontrado.", ephemeral=True); return
    subtotal, discount, total, rate, supplied_inputs = quote(item, quantidade, insumos)
    embed = discord.Embed(title=f"{item['icon']} Orçamento — {item['name']}", color=0xb7e458)
    embed.add_field(name="Quantidade", value=f"{quantidade:g} {item['unit']}")
    embed.add_field(name="Preço", value=f"{money(item['price'])}/{item['unit']}")
    embed.add_field(name="Subtotal", value=money(subtotal), inline=False)
    embed.add_field(name=f"Desconto ({rate:.0%})", value=f"− {money(discount)}")
    if supplied_inputs:
        embed.add_field(name="Insumos + taxa de 10%", value=money(supplied_inputs))
    embed.add_field(name="Total estimado", value=f"**{money(total)}**")
    embed.set_footer(text="Insumos não incluídos • orçamento sujeito à confirmação")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="solicitar", description="Cria uma ordem de serviço")
@app_commands.describe(fazenda="Nome da fazenda", campo="Número ou nome do campo", servico="Serviço ou pacote", quantidade="Hectares, horas ou viagens", insumos="Custo real dos insumos fornecidos pela empresa")
@app_commands.autocomplete(servico=item_autocomplete)
async def solicitar(interaction: discord.Interaction, fazenda: str, campo: str, servico: str, quantidade: app_commands.Range[float, 0.1, 10000.0], insumos: app_commands.Range[float, 0.0, 100000000.0] = 0):
    item = SERVICES.get(servico) or PACKAGES.get(servico)
    if not item:
        await interaction.response.send_message("Serviço não encontrado.", ephemeral=True); return
    subtotal, discount, total, _, supplied_inputs = quote(item, quantidade, insumos)
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO customers(discord_id,display_name) VALUES(?,?)", (interaction.user.id, interaction.user.display_name))
        cur = db.execute("INSERT INTO orders(customer_id,farm,field_name,item_id,item_name,quantity,unit,subtotal,discount,input_cost,total) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (interaction.user.id, farm, campo, item["id"], item["name"], quantidade, item["unit"], subtotal, discount, supplied_inputs, total))
        order_id = cur.lastrowid
    embed = discord.Embed(title=f"🚜 Ordem de Serviço #{order_id:04d}", color=0xdf7b35)
    embed.add_field(name="Cliente", value=interaction.user.mention)
    embed.add_field(name="Fazenda / Campo", value=f"{fazenda} / {campo}")
    embed.add_field(name="Serviço", value=f"{item['icon']} {item['name']}", inline=False)
    embed.add_field(name="Quantidade", value=f"{quantidade:g} {item['unit']}")
    embed.add_field(name="Valor", value=f"**{money(total)}**")
    embed.add_field(name="Status", value=STATUS["aguardando_aprovacao"], inline=False)
    channel = bot.get_channel(ORDERS_CHANNEL_ID) if ORDERS_CHANNEL_ID else interaction.channel
    if channel is None:
        await interaction.response.send_message("Não consigo acessar o canal configurado para pedidos. Verifique as permissões do FraBot.", ephemeral=True)
        return
    await channel.send(embed=embed, view=OrderView(order_id))
    await interaction.response.send_message(f"Pedido criado: **OS #{order_id:04d}**. Você pode acompanhar com `/minhas-os`.", ephemeral=True)


@bot.tree.command(name="minhas-os", description="Mostra suas ordens de serviço recentes")
async def minhas_os(interaction: discord.Interaction):
    with connect() as db:
        rows = db.execute("SELECT * FROM orders WHERE customer_id=? ORDER BY id DESC LIMIT 10", (interaction.user.id,)).fetchall()
    if not rows:
        await interaction.response.send_message("Você ainda não possui ordens de serviço.", ephemeral=True); return
    lines = [f"**#{r['id']:04d}** • {r['item_name']} • {money(r['total'])}\n{STATUS[r['status']]} — {r['farm']}, campo {r['field_name']}" for r in rows]
    await interaction.response.send_message(embed=discord.Embed(title="📋 Minhas ordens", description="\n\n".join(lines), color=0x264f35), ephemeral=True)


@bot.tree.command(name="fila", description="Mostra a fila pública de serviços")
async def fila(interaction: discord.Interaction):
    with connect() as db:
        rows = db.execute("SELECT id,item_name,farm,field_name,status FROM orders WHERE status IN ('aprovada','em_andamento') ORDER BY CASE status WHEN 'em_andamento' THEN 0 ELSE 1 END,id LIMIT 15").fetchall()
    if not rows:
        await interaction.response.send_message("A fila está vazia no momento."); return
    lines = [f"{('🚜' if r['status']=='em_andamento' else '⏳')} **#{r['id']:04d}** • {r['item_name']}\n{r['farm']}, campo {r['field_name']} — {STATUS[r['status']]}" for r in rows]
    await interaction.response.send_message(embed=discord.Embed(title="🚜 Fila de serviços", description="\n\n".join(lines), color=0x264f35))


@bot.tree.command(name="stats", description="Mostra as estatísticas da empresa")
async def stats(interaction: discord.Interaction):
    with connect() as db:
        row = db.execute("SELECT COUNT(*) total_orders,COALESCE(SUM(CASE WHEN unit='ha' AND status='concluida' THEN quantity ELSE 0 END),0) hectares,COALESCE(SUM(CASE WHEN status='concluida' THEN total ELSE 0 END),0) revenue FROM orders").fetchone()
    embed = discord.Embed(title="📊 FS25 Serviços Agrícolas", color=0xb7e458)
    embed.add_field(name="Ordens registradas", value=str(row["total_orders"]))
    embed.add_field(name="Área concluída", value=f"{row['hectares']:,.1f} ha".replace(",", "."))
    embed.add_field(name="Faturamento concluído", value=money(row["revenue"]), inline=False)
    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    if not TOKEN: raise RuntimeError("Configure DISCORD_TOKEN no arquivo bot/.env")
    setup_database()
    bot.run(TOKEN)

