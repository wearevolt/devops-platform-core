# Архитектура CLI Setup

## Обзор

Команда `poetry run cgdevxcli setup -f ../parameters.yaml` запускает полный цикл развёртывания DevOps платформы.

## Структура проекта

```
tools/cli/
├── commands/
│   └── setup.py           # Основная команда setup
├── services/
│   ├── platform_template_manager.py  # Управление шаблонами GitOps
│   ├── tf_wrapper.py                  # Обёртка для Terraform
│   ├── k8s/                           # Kubernetes клиенты
│   ├── cloud/                         # Провайдеры облака (AWS, GCP, Azure)
│   ├── vcs/                           # Git провайдеры (GitHub, GitLab)
│   └── dns/                           # DNS провайдеры
├── common/
│   ├── state_store.py     # Хранилище состояния и чекпоинты
│   ├── versions.yaml      # Версии компонентов
│   ├── const/             # Константы
│   └── enums/             # Перечисления
└── pyproject.toml
```

## Рабочие директории

```
~/.cgdevx/                    # Основная рабочая директория
├── state.yaml                # Состояние CLI (чекпоинты, параметры)
├── gitops/                   # Клонированный GitOps репозиторий
│   ├── terraform/            # Terraform модули
│   │   ├── vcs/              # VCS (GitHub/GitLab)
│   │   ├── hosting_provider/ # EKS/AKS/GKE кластер
│   │   ├── secrets/          # Vault секреты
│   │   ├── users/            # Пользователи
│   │   └── core_services/    # Harbor, SonarQube
│   └── gitops-pipelines/     # ArgoCD манифесты
└── tools/                    # Установленные инструменты
    ├── terraform
    └── kubectl
```

---

## Этапы выполнения Setup

### Диаграмма потока

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         cgdevxcli setup                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. ЗАГРУЗКА ПАРАМЕТРОВ                                                   │
│    • Чтение parameters.yaml                                             │
│    • Загрузка state.yaml (если есть)                                    │
│    • Валидация входных параметров                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. PREFLIGHT CHECKS (Checkpoint: preflight)                             │
│    • Проверка прав Cloud Provider (AWS/GCP/Azure)                       │
│    • Проверка Git токена и прав                                         │
│    • Проверка DNS (Route53/CloudFlare)                                  │
│    • Получение информации о Git пользователе                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. DEPENDENCIES CHECK (Checkpoint: dependencies)                         │
│    • Проверка/установка Terraform                                       │
│    • Проверка/установка kubectl                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. ONE-TIME SETUP (Checkpoint: one-time-setup)                          │
│    • Генерация SSH ключей (ED25519 + RSA)                               │
│    • Создание S3 bucket для Terraform state                             │
│    • Подготовка Terraform backend сниппетов                             │
│    • Получение информации о DNS зоне                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. REPO PREP (Checkpoint: repo-prep)                                    │
│    • Клонирование шаблона GitOps репозитория                            │
│    • Копирование terraform/ и gitops-pipelines/                         │
│    • Подготовка README файлов                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. PARAMETRISE (Всегда выполняется)                                     │
│    • Замена плейсхолдеров в Terraform файлах                            │
│    • Замена плейсхолдеров в GitOps манифестах                           │
│    • Пример: <PRIMARY_CLUSTER_NAME> → "pjc"                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 7. VCS PROVISIONING (Checkpoint: vcs-tf)                                │
│    terraform/vcs/                                                        │
│    • Создание GitOps репозитория                                        │
│    • Настройка webhooks для ArgoCD                                      │
│    • Настройка webhooks для Atlantis                                    │
│    • Создание bot пользователя                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 8. K8S CLUSTER (Checkpoint: k8s-tf)                                     │
│    terraform/hosting_provider/                                           │
│    • Создание VPC (или использование существующего)                     │
│    • Создание EKS кластера                                              │
│    • Создание Node Groups                                               │
│    • Создание IAM ролей (IRSA)                                          │
│    • Создание S3 buckets для artifacts и backups                        │
│    • Создание KMS ключей                                                │
│    • Генерация kubeconfig                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 9. GITOPS VCS PUSH (Checkpoint: gitops-vcs)                             │
│    • Финальная параметризация файлов                                    │
│    • git init + git push в созданный репозиторий                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 10. ARGOCD INSTALLATION (Checkpoint: k8s-delivery)                      │
│     • Создание namespace argocd                                         │
│     • Bootstrap Job (kustomize build + kubectl apply)                   │
│     • Ожидание готовности ArgoCD компонентов:                           │
│       - argocd-application-controller                                   │
│       - argocd-server                                                   │
│       - argocd-repo-server                                              │
│       - argocd-redis-ha-*                                               │
│     • Создание namespaces: argo, atlantis, external-secrets            │
│     • Создание ArgoCD credentials secret                                │
│     • Создание ArgoCD project "core"                                    │
│     • Deploy registry application (запуск синхронизации)                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 11. SECRETS MANAGEMENT (Checkpoint: secrets-management)                 │
│     • Ожидание ALB Controller                                           │
│     • Ожидание External DNS                                             │
│     • Ожидание Vault StatefulSet                                        │
│     • Инициализация Vault (vault operator init)                         │
│     • Сохранение unseal keys в K8s Secret                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 12. SECRETS TF (Checkpoint: secrets-management-tf)                      │
│     terraform/secrets/                                                   │
│     • Ожидание Vault Ingress                                            │
│     • Настройка Vault:                                                  │
│       - OIDC provider                                                   │
│       - Политики                                                        │
│       - Секреты для сервисов                                            │
│     • Создание OIDC клиентов для Harbor, SonarQube                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 13. USERS TF (Checkpoint: users-tf)                                     │
│     terraform/users/                                                     │
│     • Создание пользователей в Vault                                    │
│     • Настройка групп и политик                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 14. CORE SERVICES TF (Checkpoint: core-services-tf)                     │
│     terraform/core_services/                                             │
│     • Ожидание Harbor и SonarQube                                       │
│     • Настройка Harbor:                                                 │
│       - OIDC                                                            │
│       - Robot accounts                                                  │
│       - Proxy registries (DockerHub, GCR, Quay)                         │
│     • Настройка SonarQube:                                              │
│       - OIDC                                                            │
│       - Quality Gates                                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 15. TF STORE HARDENING (Checkpoint: tf-store-hardening)                 │
│     • Ограничение доступа к S3 bucket с Terraform state                 │
│     • Доступ только для Atlantis IAM роли                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 16. SHOW CREDENTIALS                                                     │
│     • Вывод URL и credentials для всех сервисов                         │
│     • Открытие GitOps репозитория в браузере                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Система чекпоинтов

### Как это работает

1. **StateStore** (`common/state_store.py`) хранит:
   - `checkpoints` — список пройденных этапов
   - `parameters` — плейсхолдеры для замены (`<PRIMARY_CLUSTER_NAME>`)
   - `fragments` — многострочные сниппеты (`# <TF_VCS_REMOTE_BACKEND>`)
   - `internals` — внутренние переменные (токены, пароли)
   - `input_params` — входные параметры из YAML

2. **Файл состояния** сохраняется в `~/.cgdevx/state.yaml`

3. **Проверка чекпоинта**:
```python
if not p.has_checkpoint("k8s-tf"):
    # Выполнить этап
    p.set_checkpoint("k8s-tf")
    p.save_checkpoint()
else:
    click.echo("Skipped K8s provisioning.")
```

### Список чекпоинтов

| Checkpoint | Описание |
|------------|----------|
| `preflight` | Pre-flight проверки |
| `dependencies` | Установка зависимостей |
| `one-time-setup` | SSH ключи, TF backend |
| `repo-prep` | Клонирование шаблона |
| `vcs-tf` | Terraform VCS |
| `k8s-tf` | Terraform EKS |
| `gitops-vcs` | Push в GitOps repo |
| `k8s-delivery` | Установка ArgoCD |
| `secrets-management` | Init Vault |
| `secrets-management-tf` | Terraform Vault |
| `users-tf` | Terraform Users |
| `core-services-tf` | Terraform Harbor/SonarQube |
| `tf-store-hardening` | Защита TF state |

---

## Параметризация (Placeholder Replacement)

### Процесс замены

1. **GitOpsTemplateManager.parametrise()** обходит все `.tf`, `.yaml`, `.yml`, `.md` файлы
2. Заменяет плейсхолдеры из `state.parameters` и `state.fragments`

```python
# platform_template_manager.py
def __file_replace(state: StateStore, folder):
    for root, dirs, files in os.walk(folder):
        for name in files:
            if name.endswith((".tf", ".yaml", ".yml", ".md")):
                with open(file_path, "r") as file:
                    data = file.read()
                    for k, v in state.fragments.items():
                        data = data.replace(k, v)
                    for k, v in state.parameters.items():
                        data = data.replace(k, v)
                with open(file_path, "w") as file:
                    file.write(data)
```

### Основные плейсхолдеры

| Плейсхолдер | Источник | Пример значения |
|-------------|----------|-----------------|
| `<PRIMARY_CLUSTER_NAME>` | parameters.yaml | `pjc` |
| `<DOMAIN_NAME>` | parameters.yaml | `pjc.wearevolt.com` |
| `<CLOUD_REGION>` | parameters.yaml | `us-east-2` |
| `<VPC_ID>` | parameters.yaml | `vpc-07a6f1a70d1e42320` |
| `<ACM_CERTIFICATE_ARN>` | parameters.yaml | `arn:aws:acm:...` |
| `<CD_INGRESS_URL>` | Вычисляется | `argocd.pjc.wearevolt.com` |
| `<REGISTRY_INGRESS_URL>` | Вычисляется | `harbor.pjc.wearevolt.com` |
| `<ALB_CONTROLLER_IRSA_ROLE_ARN>` | Terraform output | `arn:aws:iam::...` |
| `<KUBECTL_VERSION>` | versions.yaml | `1.34.2` |

### Формулы вычисления URL

```python
cluster_fqdn = domain_name  # pjc.wearevolt.com

p.parameters["<CD_INGRESS_URL>"] = f'argocd.{cluster_fqdn}'
p.parameters["<CI_INGRESS_URL>"] = f'argo.{cluster_fqdn}'
p.parameters["<REGISTRY_INGRESS_URL>"] = f'harbor.{cluster_fqdn}'
p.parameters["<SECRET_MANAGER_INGRESS_URL>"] = f'vault.{cluster_fqdn}'
p.parameters["<GRAFANA_INGRESS_URL>"] = f'grafana.{cluster_fqdn}'
p.parameters["<CODE_QUALITY_INGRESS_URL>"] = f'sonarqube.{cluster_fqdn}'
p.parameters["<PORTAL_INGRESS_URL>"] = f'backstage.{cluster_fqdn}'
p.parameters["<IAC_PR_AUTOMATION_INGRESS_URL>"] = f'atlantis.{cluster_fqdn}'
```

---

## Terraform Wrapper

### Структура

```python
class TfWrapper:
    def __init__(self, working_dir):
        self.terraform_bin_path = "~/.cgdevx/tools/terraform"
        self.working_dir = working_dir
    
    def init(self):   # terraform init -reconfigure
    def apply(self):  # terraform apply -auto-approve
    def output(self): # terraform output -json
    def destroy(self): # terraform destroy -auto-approve
```

### Пример использования

```python
# Создание EKS кластера
tf_wrapper = TfWrapper(LOCAL_TF_FOLDER_HOSTING_PROVIDER)
tf_wrapper.init()
tf_wrapper.apply({"cluster_ssh_public_key": public_key})
hp_out = tf_wrapper.output()

# Получение outputs
p.parameters["<CI_IAM_ROLE_RN>"] = hp_out["ci_role"]
p.parameters["<ALB_CONTROLLER_IRSA_ROLE_ARN>"] = hp_out["alb_controller_role"]
```

---

## ArgoCD Bootstrap

### Процесс установки

1. **Создание ресурсов**:
```python
kube_client.create_namespace(ARGOCD_NAMESPACE)
kube_client.create_service_account(ARGOCD_NAMESPACE, "argocd-bootstrap")
kube_client.create_cluster_role(ARGOCD_NAMESPACE, "argocd-bootstrap")
kube_client.create_cluster_role_binding(...)
```

2. **Bootstrap Job** выполняет:
```bash
kustomize build github.com:argoproj/argo-cd.git/manifests/ha/cluster-install?ref=v3.2.1 | kubectl apply -f -
```

3. **Ожидание компонентов**:
```python
argocd_server = kube_client.get_deployment(ARGOCD_NAMESPACE, "argocd-server")
kube_client.wait_for_deployment(argocd_server)
```

4. **Создание credentials**:
```python
# Repo credentials template
kube_client.create_plain_secret(
    ARGOCD_NAMESPACE,
    "org-repo-creds",
    {"type": "git", "url": "git@github.com:org/", "sshPrivateKey": key},
    labels={"argocd.argoproj.io/secret-type": "repo-creds"}
)
```

5. **Deploy registry app**:
```python
cd_man.create_core_application(
    "core",
    "git@github.com:org/gitops.git",
    exclude_list
)
```

---

## Версии компонентов

Все версии централизованы в `tools/cli/common/versions.yaml`:

```yaml
# Kubernetes tools
kubectl: "1.34.2"
terraform: "1.11.4"

# ArgoCD (installed via Kustomize)
argocd: "v3.2.1"
argo_workflows: "0.46.2"

# Core services
vault: "0.29.1"
external_secrets: "0.16.0"
external_dns: "1.19.0"

# AWS Load Balancer Controller
aws_load_balancer_controller: "1.13.4"
aws_load_balancer_controller_image_tag: "v2.11.0"

# CI/CD
atlantis: "5.23.0"
harbor: "v1.16.3"

# Monitoring
kube_prometheus_stack: "80.4.1"

# Developer Portal
backstage: "2.6.3"
sonarqube: "10.2.0"
```

---

## Отладка

### Включение DEBUG логов

```bash
poetry run cgdevxcli setup -f ../parameters.yaml --verbosity DEBUG
```

### Перезапуск с определённого этапа

```bash
# Удалить state.yaml для полного перезапуска
rm ~/.cgdevx/state.yaml

# Или отредактировать state.yaml, убрав нужные чекпоинты
```

### Проверка состояния

```bash
cat ~/.cgdevx/state.yaml
```

### Ручная параметризация

Если плейсхолдеры не заменены:
```bash
cd ~/.cgdevx/gitops
find . -name "*.yaml" | xargs sed -i '' 's/<PLACEHOLDER>/value/g'
git add -A && git commit -m "fix: replace placeholders" && git push
```

---

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `CGDEVX_LOCAL_FOLDER` | Рабочая директория (default: `~/.cgdevx`) |
| `CGDEVX_CLI_CLONE_LOCAL` | Использовать локальные файлы вместо git clone |
| `AWS_PROFILE` | AWS профиль для аутентификации |

---

## Полезные команды

```bash
# Запуск setup
cd tools/cli
poetry run cgdevxcli setup -f ../parameters.yaml --verbosity DEBUG

# Destroy (обратный процесс)
poetry run cgdevxcli destroy -f ../parameters.yaml

# Проверка состояния кластера
export AWS_PROFILE=pjc
kubectx pjc
kubectl get pods -A

# Проверка ArgoCD приложений
kubectl get applications -n argocd
```

