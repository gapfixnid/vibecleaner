export type ProviderStage = "detection" | "ocr" | "translation" | "inpainting" | "rendering";
export type ProviderResourceClass = "cpu" | "gpu" | "io" | "network";
export type ProviderConfigValueType = "string" | "integer" | "number" | "boolean" | "enum" | "secret";

export interface ProviderConfigFieldDto {
  key: string;
  value_type: ProviderConfigValueType;
  label: string;
  required: boolean;
  default: unknown;
  choices: string[];
  advanced: boolean;
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
}

export interface ProviderCatalogDto {
  schema_version: number;
  providers: ProviderManifestDto[];
}
