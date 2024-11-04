import pandas as pd
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load exchange rates from CSV
CSV_FILE_PATH = 'exchange_rates.csv'
exchange_data = pd.read_csv(CSV_FILE_PATH)

# Extract unique origin options for the keyboard and drop NaN values
origin_options = exchange_data['Origen'].dropna().unique()

# Define custom keyboards
def format_keyboard(options, row_width=3):
    return [options[i:i + row_width] for i in range(0, len(options), row_width)]

final_options_keyboard = [["Continuar con la transacción", "Realizar otra consulta"]]

# Function to get dólar blue rates
def obtener_cotizacion_dolar_blue():
    url = "https://api.bluelytics.com.ar/v2/latest"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return data["blue"]["value_buy"], data["blue"]["value_sell"]
    else:
        return None, None

# Start command with compact keyboard
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Set stage to 'origin' to indicate the next step
    context.user_data['stage'] = 'origin'
    origin_keyboard = format_keyboard(list(origin_options), row_width=3)
    
    await update.message.reply_text(
        "¡Bienvenido! Selecciona la moneda o saldo que deseas cambiar (Origen).",
        reply_markup=ReplyKeyboardMarkup(origin_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

# Handle user messages based on the current stage
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Get the current stage
    stage = context.user_data.get('stage')
    message_text = update.message.text.strip().lower()

    if stage == 'origin':
        # Store origin currency and prompt for destination
        context.user_data['origin'] = message_text
        context.user_data['stage'] = 'destination'
        
        # Filter destinations based on selected origin
        destination_options = exchange_data[exchange_data['Origen'] == message_text]['Destino'].dropna().unique()
        destination_keyboard = format_keyboard(list(destination_options), row_width=3)
        
        await update.message.reply_text(
            "Selecciona la moneda o saldo que deseas recibir (Destino).",
            reply_markup=ReplyKeyboardMarkup(destination_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
    
    elif stage == 'destination':
        # Store destination currency and prompt for amount
        context.user_data['destination'] = message_text
        context.user_data['stage'] = 'amount'
        
        await update.message.reply_text("Ingresa el monto que deseas cambiar.")

    elif stage == 'amount':
        # Calculate the exchange based on origin, destination, and amount
        try:
            amount = float(message_text)
            origin = context.user_data.get('origin')
            destination = context.user_data.get('destination')
            
            # Fetch dólar blue rates
            dolar_blue_compra, dolar_blue_venta = obtener_cotizacion_dolar_blue()
            
            if dolar_blue_compra is None or dolar_blue_venta is None:
                await update.message.reply_text("Error al obtener la cotización del dólar blue.")
                return
            
            # Determine if we need to apply dólar blue rate
            if "pesos" in origin:
                exchange_rate = dolar_blue_venta
            elif "pesos" in destination:
                exchange_rate = dolar_blue_compra
            else:
                exchange_rate = 1  # No conversion needed if pesos isn't involved
            
            # Find the commission rate for the selected origin and destination
            rate_row = exchange_data[(exchange_data['Origen'] == origin) & (exchange_data['Destino'] == destination)]
            
            if rate_row.empty:
                await update.message.reply_text("No se encontró una tasa de cambio para esta combinación.")
                return
            
            # Calculate the result using the corrected formula
            commission_final = float(rate_row.iloc[0]['comision final'])
            result = amount * (commission_final / 100) * exchange_rate
            
            await update.message.reply_text(
                f"El cambio de {amount} {origin.upper()} a {destination.upper()} es {result:.2f}."
            )
            
            # Provide final options: continue or start a new query
            context.user_data['stage'] = 'final'
            await update.message.reply_text(
                "¿Deseas continuar con la transacción o realizar otra consulta?",
                reply_markup=ReplyKeyboardMarkup(final_options_keyboard, one_time_keyboard=True, resize_keyboard=True)
            )
            
        except ValueError:
            await update.message.reply_text("Por favor ingresa un monto válido en números.")

    elif stage == 'final':
        if message_text == "continuar con la transacción":
            await update.message.reply_text(
                "Serás derivado a un operador para continuar con la transacción. ¡Gracias!"
            )
            # Reset stage for a new query if needed later
            context.user_data['stage'] = 'origin'
        elif message_text == "realizar otra consulta":
            # Restart the bot with origin selection
            await start(update, context)

# Main function to run the bot
def main():
    application = Application.builder().token("8100061827:AAHIlfYjzJjuGNhihy_YZHM98jmeSl_QeHg").build()
    
    # Add handlers for the bot
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
