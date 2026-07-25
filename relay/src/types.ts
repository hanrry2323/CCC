// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — 共享类型定义
// ═══════════════════════════════════════════════════════════════

// ── Tier ──
export type TierId = "pro" | "flash" | "code";
export const TIERS: TierId[] = ["pro", "flash", "code"];

export const TIER_LABELS: Record<TierId, string> = {
  pro: "Pro (High Capability)",
  flash: "Flash (Fast & Balanced)",
  code: "Code (Free Tier)",
};

export interface TierCapabilities {
  max_context: number;
  supports_tools: boolean;
  supports_images: boolean;
  supports_thinking: boolean;
  max_output_tokens: number;
}

// ── Upstream ──
export interface UpstreamConfig {
  name: string;
  base_url: string;
  api_key: string;
  tier: TierId;
  tier_priority: number;
  models: TierId[];
  upstream_model: string;
  fallback_model?: string;
  capabilities?: Partial<TierCapabilities>;
  /** 上游配额；未配置的维度不限制。daily_tokens 兼容旧配置，等价于 tpd */
  quota?: {
    daily_tokens?: number;
    rpm?: number;
    rpd?: number;
    tpm?: number;
    tpd?: number;
  };
  primary?: boolean;
  free?: boolean;
  free_type?: "recurring-daily" | "recurring-monthly" | "recurring-credit" | "recurring-uncapped" | "one-time-initial" | "keyless" | "discontinued";
  free_tokens_monthly?: number;
  free_pool_key?: string;
  enabled?: boolean;
  // v3.6+: 上游请求级字段覆盖 (e.g. { thinking: { type: "disabled" } })
  // 通过 spread 注入到请求 body 中, 不参与路由, 仅字段透传
  request_overrides?: Record<string, unknown>;
  // v3.6+ (预留): 上游协议类型 — openai-chat 默认; anthropic = 上游是 Anthropic 兼容端点
  wire_protocol?: "openai-chat" | "anthropic";
  // v4.1: 所属 provider 分组（用于断路器，同组上游共享 break threshold）
  provider_group?: string;
  // 透传字段, 不参与路由, 仅审计 / dashboard
  _note?: string;
}

// ── Routing ──
export interface RoutingResult {
  upstream: UpstreamConfig | null;
  candidates: UpstreamConfig[];
  tier: TierId;
  is_fallback: boolean;
  fallback_model: string | null;
}

// ── Health ──
export type HealthStatus = "healthy" | "ratelimit" | "unhealthy" | "down" | "none";

export interface HealthRecord {
  status: HealthStatus;
  latency_ms: number;
  timestamp: number;
  error?: string;
}

// ── Cooldown ──
export interface CooldownRecord {
  until: number;     // Date.now() + duration_ms
  reason: string;
}

// ── Health Score (v3.6) ──
export interface ScoreRecord {
  ewma: number;          // 0..1, EWMA 平滑成功率，初值 0.5
  recentTs: number;      // 最近一次更新时间
  failStreak: number;    // 连续失败次数（用于指数退避）
  lastSuccessTs: number; // 上次成功时间
  totalSuccess: number;  // 累计成功
  totalFail: number;     // 累计失败
}

// ── Auth ──
export interface ClientConfig {
  id: string;
  key: string;
  name?: string;
  models?: string[];
  quota?: { daily_tokens: number };
  active?: boolean;
}

export interface AuthenticatedClient {
  id: string;
  name: string;
  models?: string[];
  qe?: boolean;       // quota exceeded
}

// ── Request Types (Anthropic) ──
export interface AnthropicMessage {
  role: "user" | "assistant" | "tool";
  content: string | ContentBlock[];
  tool_use_id?: string;
  tool_calls?: ToolCall[];
}

export interface ContentBlock {
  type: "text" | "image" | "tool_use" | "tool_result" | "redacted_thinking";
  text?: string;
  id?: string;
  name?: string;
  input?: Record<string, unknown>;
  tool_use_id?: string;
  content?: string;
  data?: string;
  source?: { type: string; media_type: string; data: string };
  cache_control?: { type: "ephemeral" };  // Anthropic prompt caching breakpoint
}

export interface ToolCall {
  id: string;
  type: "function";
  function: { name: string; arguments: string };
}

export interface AnthropicTool {
  name: string;
  description?: string;
  input_schema?: Record<string, unknown>;
}

export interface ToolChoice {
  type: "auto" | "any" | "tool";
  name?: string;
}

export interface AnthropicRequest {
  model: string;
  messages: AnthropicMessage[];
  system?: string | ContentBlock[];
  tools?: AnthropicTool[];
  tool_choice?: ToolChoice;
  max_tokens: number;
  stream?: boolean;
  temperature?: number;
  top_p?: number;
  stop_sequences?: string[];
}

// ── Request Types (OpenAI Chat) ──
export interface ChatMessage {
  role: "system" | "developer" | "user" | "assistant" | "tool";
  content: string | null | Record<string, unknown>[];
  tool_call_id?: string;
  tool_calls?: OpenAIToolCall[];
  reasoning_content?: string;
}

export interface OpenAIToolCall {
  id: string;
  type: "function";
  function: { name: string; arguments: string };
  index?: number;
}

export interface OpenAIFunctionTool {
  type: "function";
  function: {
    name: string;
    description?: string;
    parameters?: Record<string, unknown>;
  };
}

export interface OpenAIChatRequest {
  model: string;
  messages: ChatMessage[];
  tools?: OpenAIFunctionTool[];
  tool_choice?: string | Record<string, unknown>;
  max_tokens?: number;
  stream?: boolean;
  temperature?: number;
  top_p?: number;
  stop?: string[];
  stream_options?: { include_usage: boolean };
}

// ── Request Types (OpenAI Responses) ──
export type InputItem =
  | { type: "input_text"; text: string }
  | { type: "function_call_output"; call_id: string; output: string }
  | { type: "function_call"; call_id: string; name: string; arguments: string }
  | { type: "message"; role: string; content: string | ContentBlock[] }
  | { role?: string; content?: string; tool_call_id?: string; tool_calls?: OpenAIToolCall[] };

export interface OpenAIResponsesRequest {
  model: string;
  input: InputItem[];
  tools?: OpenAIFunctionTool[];
  max_output_tokens?: number;
  stream?: boolean;
  temperature?: number;
}

// ── Upstream Response Types ──
export interface OpenAICompletionChoice {
  index: number;
  delta?: { content?: string; tool_calls?: OpenAIToolCall[]; role?: string };
  message?: { content?: string; tool_calls?: OpenAIToolCall[]; role?: string; reasoning_content?: string };
  finish_reason: string | null;
  usage?: OpenAIUsage;
}

export interface OpenAIUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  output_tokens?: number;
  prompt_tokens_details?: { cached_tokens?: number };
}

export interface OpenAIChunk {
  choices?: OpenAICompletionChoice[];
  usage?: OpenAIUsage;
  error?: { message: string; type?: string; code?: string };
}

export interface OpenAIResponse {
  choices: OpenAICompletionChoice[];
  usage?: OpenAIUsage;
  error?: { message: string; type?: string; code?: string };
}

// ── Anthropic SSE Events ──
export type AnthropicSSEEvent =
  | { type: "message_start"; message: Record<string, unknown> }
  | { type: "content_block_start"; index: number; content_block: Record<string, unknown> }
  | { type: "content_block_delta"; index: number; delta: Record<string, unknown> }
  | { type: "content_block_stop"; index: number }
  | { type: "message_delta"; delta: Record<string, unknown>; usage?: Record<string, unknown> }
  | { type: "message_stop" }
  | { type: "ping" };

// ── Cache ──
export interface CacheEntry {
  key: string;
  response: unknown;
  timestamp: number;
  tokens: { input: number; output: number };
  ttl_ms: number;
}

// ── Free Model Catalog ──
export interface FreeModelEntry {
  provider: string;
  model_id: string;
  display_name: string;
  monthly_tokens: number;
  credit_tokens?: number;
  free_type: "recurring-daily" | "recurring-monthly" | "recurring-credit" | "recurring-uncapped" | "one-time-initial" | "keyless" | "discontinued";
  pool_key: string | null;
  tos: "ok" | "caution" | "ambiguous" | "avoid";
}

// ── Usage Log ──
export interface UsageRecord {
  timestamp: number;
  upstream: string;
  client: string;
  model: string;
  total_tokens: number;
  cached_tokens?: number;
  success: boolean;
  latency_ms: number;
}

// ── Failover trail (v4.2) ──
export interface FallbackAttempt {
  name: string;
  reason: string;
  ms: number;
  at: number;
}

export interface TrailRecord {
  at: number;
  tier: string;
  ok: boolean;
  routed?: string;
  trail: FallbackAttempt[];
}

// ── Error Classification ──
export interface ClassifiedError {
  sec: number;    // cooldown seconds
  quota: boolean; // true = quota exceeded, false = rate limit / network
}

// ── Server Options ──
export type ServerMode = "anthropic" | "openai-chat" | "openai-responses" | "all";

export interface ServerOptions {
  port: number;
  mode: ServerMode;
}
