import docker

# Подключаемся к локальному Docker-демону
client = docker.from_env()

IMAGE_NAME = "comfyui-base:latest"  # <-- ЗАМЕНИ на имя твоего собранного образа ComfyUI
PORT = 8188

print(f"Пытаемся запустить {IMAGE_NAME} на порту {PORT}...")

try:
    container = client.containers.run(
        image=IMAGE_NAME,
        detach=True,
        ports={'8188/tcp': PORT},
        # Вот эта строчка критически важна для NVIDIA A100
        device_requests=[
            docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
        ],
        name="test_comfyui_instance",
        auto_remove=True  # Контейнер сам удалится при остановке, чтобы не мусорить
    )

    print(f"✅ Успех! Контейнер запущен. ID: {container.id[:10]}")
    print(f"Перейди в браузер: http://<ip-твоего-сервера>:{PORT}")
    print("Чтобы остановить его, выполни в терминале: docker stop test_comfyui_instance")

except docker.errors.ImageNotFound:
    print(f"❌ Ошибка: Образ '{IMAGE_NAME}' не найден. Ты его собрал?")
except docker.errors.APIError as e:
    print(f"❌ Ошибка Docker API:\n{e}")
except Exception as e:
    print(f"❌ Неизвестная ошибка:\n{e}")