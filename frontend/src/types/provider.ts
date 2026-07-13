export type ProviderStage = "detection" | "ocr" | "translation" | "inpainting" | "rendering";
export type ProviderResourceClass = "cpu" | "gpu" | "io" | "network";
export type ProviderConfigValueType = "string" | "integer" | "number" | "boolean" | "enum" | "secret" | "model";

export interface ProviderConfigFieldDto {
  key: string;
  value_type: ProviderConfigValueType;
  label: string;
  required: boolean;
  default: unknown;
  choices: string[];
  choice_labels: string[];
  advanced: boolean;
  placeholder: string | null;
  help_text: string | null;
  minimum: number | null;
  maximum: number | null;
  step: number | null;
  visible_when_key: string | null;
  visible_when_value: unknown;
}

export interface ProviderCapabilitiesDto {
  languages: string[];
  devices: string[];
  execution_modes: string[];
  features: string[];
  supports_batch: boolean;
}

export interface ProviderManifestDto {
  provider_id: string;
  display_name: string;
  stage: ProviderStage;
  api_version: string;
  implementation_version: string;
  capabilities: ProviderCapabilitiesDto;
  resource_classes: ProviderResourceClass[];
  max_concurrency: number;
  config_schema: ProviderConfigFieldDto[];
  legacy_adapter: boolean;
  selection_value: string;
  description: string;
  catalog_order: number;
}

export interface ProviderCatalogDto {
  schema_version: number;
  providers: ProviderManifestDto[];
}
