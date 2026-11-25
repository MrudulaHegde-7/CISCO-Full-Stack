# Architecture and use cases

## Runtime architecture

```mermaid
flowchart LR
    Browser[HTML CSS JavaScript] -->|same-origin Fetch + Basic Auth| API[FastAPI routers]
    API --> Auth[Authentication and authorization]
    API --> Catalog[Catalog service]
    API --> Orders[Order service]
    API --> Chat[Chat and action services]
    API --> Documents[Document service]
    Catalog --> MenuRepo[Menu repository protocol]
    Orders --> OrderRepo[Order repository protocol]
    Chat --> ChatRepo[Chat repository protocol]
    Documents --> DocumentRepo[Document repository protocol]
    MenuRepo --> MySQL[(MySQL)]
    OrderRepo --> MySQL
    ChatRepo --> MySQL
    DocumentRepo --> MySQL
    Chat --> Gemini[Gemini adapter]
    Gemini -->|allowlisted tools, fixed local API paths| API
    Documents --> Extract[PDF DOCX TXT extraction]
    Extract --> Embed[Gemini embeddings]
    Embed --> Chroma[(Persistent ChromaDB)]
    Chat --> Chroma
```

The browser and Gemini agent use the same validated API and service rules. RAG retrieves active document chunks only; it is not a source of live inventory. Services depend on repository/gateway protocols, while SQLAlchemy, MySQL, Chroma, and Gemini are replaceable adapters. The FastAPI request session is the unit of work for order, stock, and line-item changes.

## Use cases

```mermaid
flowchart LR
    Guest([Guest]) --> Browse[Browse and filter active menu]
    Guest --> PublicPolicy[Ask public/general questions]
    Customer([Authenticated customer]) --> Browse
    Customer --> Orders[Create and view own orders]
    Customer --> Cancel[Request cancellation]
    Customer --> Chat[Create and reopen chat sessions]
    Chat --> ReadTools[Search live menu and order status]
    Chat --> Policy[RAG policy answers with citations]
    Chat --> Pending[Prepare pending create/cancel action]
    Pending --> Confirm{Explicit confirmation?}
    Confirm -->|Yes| Orders
    Confirm -->|No| Reject[Record rejection; do not mutate]
    Admin([Administrator]) --> Catalog[Create, edit, delete or archive menu items]
    Admin --> Knowledge[Upload and re-index policy documents]
    Admin --> Status[Advance permitted order statuses]
```