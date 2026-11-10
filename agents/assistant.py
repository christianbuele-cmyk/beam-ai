from memory.memory_store import load_memory, save_memory
from agents.llm_agent import ask_llm


class AssistantAgent:

    def process(
        self,
        message: str,
        session_key: str,
        tone: str = "Profesional",
        agent_name: str = "BEAM AI",
        profile=None
    ):

        memory = load_memory(session_key)
        memory_enabled = memory.get("enabled", True)

        history = memory.get("history", []) if memory_enabled else []

        if not isinstance(history, list):
            history = []

        if memory_enabled and message.lower().startswith("me llamo"):
            name = message[8:].strip()
            memory["name"] = name

        history.append({
            "role": "user",
            "content": message
        })

        context = ""

        for item in history[-10:]:
            context += f"{item['role']}: {item['content']}\n"

        personal_context = ""

        if isinstance(profile, dict) and profile.get("personalization_enabled", True):

            profile_parts = []

            about = str(profile.get("about", "")).strip()
            age_range = str(profile.get("age_range", "")).strip()

            interests = profile.get("interests", [])
            favorite_activities = profile.get("favorite_activities", [])
            activities_companion = str(
                profile.get("activities_companion", "")
            ).strip()
            activities_time = str(
                profile.get("activities_time", "")
            ).strip()

            travel_style = profile.get("travel_style", [])
            travel_leisure = profile.get("travel_leisure", [])
            travel_food = profile.get("travel_food", [])

            restrictions_food = profile.get("restrictions_food", [])
            restrictions_avoid = profile.get("restrictions_avoid", [])
            restrictions_accessibility = profile.get(
                "restrictions_accessibility",
                {}
            )

            if about:
                profile_parts.append(
                    f"Información proporcionada por el usuario: {about}"
                )

            if age_range:
                profile_parts.append(
                    f"Rango de edad: {age_range}"
                )

            if isinstance(interests, list) and interests:
                clean_interests = [
                    str(item).replace("custom:", "", 1)
                    for item in interests
                ]
                profile_parts.append(
                    "Intereses y aficiones: "
                    + ", ".join(clean_interests)
                )

            if isinstance(favorite_activities, list) and favorite_activities:
                profile_parts.append(
                    "Actividades favoritas: "
                    + ", ".join(map(str, favorite_activities))
                )

            if activities_companion:
                profile_parts.append(
                    f"Suele hacer planes con: {activities_companion}"
                )

            if activities_time:
                profile_parts.append(
                    f"Momento del día preferido: {activities_time}"
                )

            if isinstance(travel_style, list) and travel_style:
                profile_parts.append(
                    "Estilo de viaje preferido: "
                    + ", ".join(map(str, travel_style))
                )

            if isinstance(travel_leisure, list) and travel_leisure:
                profile_parts.append(
                    "Planes y ocio preferidos: "
                    + ", ".join(map(str, travel_leisure))
                )

            if isinstance(travel_food, list) and travel_food:
                profile_parts.append(
                    "Preferencias gastronómicas: "
                    + ", ".join(map(str, travel_food))
                )

            if isinstance(restrictions_food, list) and restrictions_food:
                profile_parts.append(
                    "Restricciones alimentarias: "
                    + ", ".join(map(str, restrictions_food))
                )

            if isinstance(restrictions_avoid, list) and restrictions_avoid:
                profile_parts.append(
                    "Prefiere evitar: "
                    + ", ".join(map(str, restrictions_avoid))
                )

            if isinstance(restrictions_accessibility, dict):
                enabled_accessibility = [
                    str(key)
                    for key, enabled
                    in restrictions_accessibility.items()
                    if enabled is True
                ]

                if enabled_accessibility:
                    profile_parts.append(
                        "Necesidades de accesibilidad o viaje: "
                        + ", ".join(enabled_accessibility)
                    )

            if profile_parts:
                personal_context = """
Perfil y preferencias proporcionadas por el usuario:
- """ + "\n- ".join(profile_parts) + """

Utiliza estos datos cuando sean relevantes para personalizar recomendaciones y respuestas.
Respeta especialmente las restricciones alimentarias, necesidades de accesibilidad y cosas que el usuario prefiere evitar.
No menciones datos personales innecesariamente.
No inventes preferencias ni atribuyas al usuario opciones que no estén guardadas.
Cuando el usuario pregunte qué sabes sobre él, puedes resumir la información que haya decidido proporcionar.
"""
        prompt = f"""
{personal_context}

Historial de conversación:

{context}

Usuario:
{message}
"""
        response = ask_llm(
            prompt,
            tone=tone,
            agent_name=agent_name
        )

        if memory_enabled:
            history.append({
                "role": "assistant",
                "content": response
            })

            memory["history"] = history

            print("NOMBRE DEL AGENTE EN ASSISTANT:", agent_name)
            print("GUARDANDO MEMORIA")
            print(memory)

            save_memory(memory, session_key)

            print("MEMORIA GUARDADA")
        else:
            print("MEMORIA DESACTIVADA - historial no guardado")

        return response