class CalculatorAgent:

    def process(self, message):

        try:

            expression = (
                message.lower()
                .replace("calcula", "")
                .strip()
            )

            result = eval(expression)

            return f"Resultado: {result}"

        except Exception:
            return None