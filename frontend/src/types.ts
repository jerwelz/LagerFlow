// Mirrors the response schemas in app/schemas.py.

export type MovementType = "IN" | "OUT";

export interface Product {
  id: number;
  sku: string;
  name: string;
  description: string | null;
  current_stock: number;
  min_stock: number;
  is_active: boolean;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Movement {
  id: number;
  product_id: number;
  movement_type: MovementType;
  quantity: number;
  reason: string | null;
  created_at: string;
}

export interface StockLevel {
  id: number;
  sku: string;
  name: string;
  current_stock: number;
  min_stock: number;
  is_low: boolean;
}

export interface InventorySummary {
  active_products: number;
  total_units: number;
  low_stock_products: number;
  out_of_stock_products: number;
}

export interface DemoInfo {
  demo_mode: boolean;
  next_reset_at: string;
  reset_interval_minutes: number;
  limits: { max_products: number; max_movements: number; writes_per_minute: number };
}

export interface ProductInput {
  sku: string;
  name: string;
  description: string | null;
  min_stock: number;
}
