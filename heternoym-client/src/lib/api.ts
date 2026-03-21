import getClient from "./client";

export interface ApiService {
  ping(): Promise<string>;
  authPing(): Promise<string>;
}

export interface TorchModel {
  id: string;
  name: string;
  hf_name: string;
  path: string;
  scan_status: string;
  scan_results: Record<string, any>;
}

export interface TorchModelCreation {
  name: string;
  hf_name: string;
  path: string;
}

export interface ModelApiService {
  create(modelCreation: TorchModelCreation): Promise<{id: string}>;
  getAll(): Promise<TorchModel[]>;
  getById(modelId: string): Promise<TorchModel>;
  delete(modelId: string): Promise<void>;
  search(hf_name: string | null, name: string | null, scan_status: string | null, items_per_page: number, page_idx: number): Promise<{
	items: TorchModel[],
	total: number,
  }>;
}

export interface ScannerRequest {
  model_id: string;
  test_on_offload_device?: boolean;
  warmup_steps?: number;
  sampling_steps?: number;
}

export interface ScannerResponse {
  message: string;
  model_id: string;
}

export interface ScanStatusResponse {
  status: string;
}

export interface QueueSizeResponse {
  queue_size: number;
}

export interface OrderInQueueResponse {
  order_in_queue: number;
}

export interface ScannerApiService {
  requestScan(
    modelId: string,
    testOnOffloadDevice?: boolean,
    warmupSteps?: number,
    samplingSteps?: number
  ): Promise<ScannerResponse>;
  getScanStatus(modelId: string): Promise<ScanStatusResponse>;
  getQueueSize(): Promise<QueueSizeResponse>;
  getOrderInQueue(modelId: string): Promise<OrderInQueueResponse>;
}

export interface OffloadConfig {
  id: number;
  model_id: number;
  name: string;
  offload_layers: string;
  // 量化参数
  quantize: boolean;
  quantize_dtype: string;
  enable_scale: boolean;
  enable_bias: boolean;
}

export interface OffloadConfigCreation {
  model_id: number;
  name: string;
  offload_layers: string;
  // 量化参数
  quantize: boolean;
  quantize_dtype: string;
  enable_scale: boolean;
  enable_bias: boolean;
  enable_fp8: boolean; // 保持向后兼容
}

export interface OffloadConfigUpdate {
  name?: string;
  offload_layers?: string;
  // 量化参数
  quantize?: boolean;
  quantize_dtype?: string;
  enable_scale?: boolean;
  enable_bias?: boolean;
  enable_fp8?: boolean; // 保持向后兼容
}

export interface OffloadConfigApiService {
  createOffloadConfig(configCreation: OffloadConfigCreation): Promise<OffloadConfig>;
  getOffloadConfig(configId: number): Promise<OffloadConfig>;
  getOffloadConfigsByModel(modelId: number): Promise<OffloadConfig[]>;
  updateOffloadConfig(configId: number, configUpdate: OffloadConfigUpdate): Promise<OffloadConfig>;
  deleteOffloadConfig(configId: number): Promise<void>;
  downloadOffloadConfig(configId: number): Promise<DownloadOffloadConfigResponse>;
}

export interface DownloadOffloadConfigResponse {
  quantization: {
    quantize: boolean;
    quantize_dtype: string;
    enable_scale: boolean;
    enable_bias: boolean;
  };
  offload: any;
}

export interface StrategyGeneratorApiService {
  getStrategyNames(): Promise<string[]>;
  generateStrategy(strategyName: string, scanResult: string, quantization: boolean): Promise<any[]>;
}

function addTorchModelApiMethods(apiService: ApiService & Partial<ModelApiService> & Partial<ScannerApiService> & Partial<OffloadConfigApiService>, remoteAddress: string, client: any): void {
	// Ensure the URL doesn't end with a slash
	const baseUrl = ((s: string) => {
		const url = remoteAddress.endsWith('/') ? remoteAddress.slice(0, -1) : remoteAddress;
		// 如果没有 http 协议头加上
		return url.startsWith('http') ? url : `http://${url}`;
	})(remoteAddress)
	apiService.create = async function(modelCreation: TorchModelCreation): Promise<{id: string}> {
		try {
			const response = await client.post(`${baseUrl}/torch-model/create`, modelCreation);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to create model: ${error}`);
		}
	};

	apiService.getAll = async function(): Promise<TorchModel[]> {
		try {
			const response = await client.get(`${baseUrl}/torch-model/all`);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to get models: ${error}`);
		}
	};


// @torch_model_router.get("/search")
// async def search_torch_models(
//     hf_name: Optional[str], name: Optional[str], scan_status: Optional[str], items_per_page: int, page_idx: int, db: Session = Depends(get_db)
// ) -> List[TorchModelResponse]:
//     logger.info(f"Searching for torch models with hf_name={hf_name}, name={name}, scan_status={scan_status}")
//     logger.info(f"Searching torch models with hf_name={hf_name}, name={name}, scan_status={scan_status}")
//     models = db.query(TorchModel).filter(
//         (TorchModel.hf_name.like(f"%{hf_name}%") if hf_name else True),
//         (TorchModel.name.like(f"%{name}%") if name else True),
//         (TorchModel.scan_status.like(f"%{scan_status}%") if scan_status else True),
//     ).offset(page_idx * items_per_page).limit(items_per_page).all
//     logger.info(f"Retrieved {len(models)} torch models")
//     result = [
//         TorchModelResponse(
//             id=model.id,
//             hf_name=model.hf_name,
//             name=model.name,
//             path=model.path,
//             scan_status=model.scan_status,
//             scan_results=model.scan_results,
//         )
//         for model in models
//     ]
//     logger.debug("Successfully formatted all torch models for response")
//     return result

	apiService.search = async (hf_name: string | null, name: string | null, scan_status: string | null, items_per_page: number, page_idx: number) => { 
		const resp = await client.get(`${baseUrl}/torch-model/search`, {
			params: {
				hf_name,
				name,
				scan_status,
				items_per_page,
				page_idx,
			},
		});
		return resp.data;
	};

	apiService.getById = async function(modelId: string): Promise<TorchModel> {
		try {
			const response = await client.get(`${baseUrl}/torch-model/${modelId}`);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to get model: ${error}`);
		}
	};

	apiService.delete = async function(modelId: string): Promise<void> {
		try {
			await client.delete(`${baseUrl}/torch-model/${modelId}`);
		} catch (error) {
			throw new Error(`Failed to delete model: ${error}`);
		}
	};
}

/**
 * 向现有的 ApiService 实例添加 Scanner 相关的 API 方法
 * @param apiService - 要扩展的 ApiService 实例（可部分实现）
 * @param remoteAddress - 远程服务器地址
 */
function addScannerApiMethods(apiService: ApiService & Partial<ModelApiService> & Partial<ScannerApiService> & Partial<OffloadConfigApiService>, remoteAddress: string, client: any): void {
	// Ensure the URL doesn't end with a slash
	const baseUrl = ((s: string) => {
		const url = remoteAddress.endsWith('/') ? remoteAddress.slice(0, -1) : remoteAddress;
		// 如果没有 http 协议头加上
		return url.startsWith('http') ? url : `http://${url}`;
	})(remoteAddress)

	// 添加扫描相关的方法
	apiService.requestScan = async function(
		modelId: string,
		testOnOffloadDevice: boolean = true,
		warmupSteps: number = 10,
		samplingSteps: number = 10
	): Promise<{ message: string; model_id: string }> {
		try {
			const response = await client.post(`${baseUrl}/scanner/request-scan`, null, {
				params: {
					model_id: modelId,
					test_on_offload_device: testOnOffloadDevice,
					warmup_steps: warmupSteps,
					sampling_steps: samplingSteps
				}
			});
			return response.data;
		} catch (error) {
			throw new Error(`Failed to request scan: ${error}`);
		}
	};
	
	apiService.getScanStatus = async function(modelId: string): Promise<{ status: string }> {
		try {
			const response = await client.get(`${baseUrl}/scanner/get-scan-status/${modelId}`);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to get scan status: ${error}`);
		}
	};
	
	apiService.getQueueSize = async function(): Promise<{ queue_size: number }> {
		try {
			const response = await client.get(`${baseUrl}/scanner/get-queue-size`);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to get queue size: ${error}`);
		}
	};
	
	apiService.getOrderInQueue = async function(modelId: string): Promise<{ order_in_queue: number }> {
		try {
			const response = await client.get(`${baseUrl}/scanner/get-order-in-queue/${modelId}`);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to get order in queue: ${error}`);
		}
	};
}

/**
 * 向现有的 ApiService 实例添加 OffloadConfig 相关的 API 方法
 * @param apiService - 要扩展的 ApiService 实例（可部分实现）
 * @param remoteAddress - 远程服务器地址
 */
function addOffloadConfigApiMethods(apiService: ApiService & Partial<ModelApiService> & Partial<ScannerApiService> & Partial<OffloadConfigApiService> & Partial<StrategyGeneratorApiService>, remoteAddress: string, client: any): void {
	// Ensure the URL doesn't end with a slash
	const baseUrl = ((s: string) => {
		const url = remoteAddress.endsWith('/') ? remoteAddress.slice(0, -1) : remoteAddress;
		// 如果没有 http 协议头加上
		return url.startsWith('http') ? url : `http://${url}`;
	})(remoteAddress)

	apiService.createOffloadConfig = async function(configCreation: OffloadConfigCreation): Promise<OffloadConfig> {
		try {
			const response = await client.post(`${baseUrl}/offload-config/create`, configCreation);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to create offload config: ${error}`);
		}
	};

	apiService.getOffloadConfig = async function(configId: number): Promise<OffloadConfig> {
		try {
			const response = await client.get(`${baseUrl}/offload-config/${configId}`);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to get offload config: ${error}`);
		}
	};

	apiService.getOffloadConfigsByModel = async function(modelId: number): Promise<OffloadConfig[]> {
		try {
			const response = await client.get(`${baseUrl}/offload-config/model/${modelId}`);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to get offload configs by model: ${error}`);
		}
	};

	apiService.updateOffloadConfig = async function(configId: number, configUpdate: OffloadConfigUpdate): Promise<OffloadConfig> {
		try {
			const response = await client.put(`${baseUrl}/offload-config/${configId}`, configUpdate);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to update offload config: ${error}`);
		}
	};

	apiService.deleteOffloadConfig = async function(configId: number): Promise<void> {
		try {
			await client.delete(`${baseUrl}/offload-config/${configId}`);
		} catch (error) {
			throw new Error(`Failed to delete offload config: ${error}`);
		}
	};
	
	apiService.downloadOffloadConfig = async function(configId: number): Promise<DownloadOffloadConfigResponse> {
		try {
			const response = await client.get(`${baseUrl}/offload-config/download/${configId}`);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to download offload config: ${error}`);
		}
	};
}

/**
 * 向现有的 ApiService 实例添加 StrategyGenerator 相关的 API 方法
 * @param apiService - 要扩展的 ApiService 实例（可部分实现）
 * @param remoteAddress - 远程服务器地址
 */
function addStrategyGeneratorApiMethods(apiService: ApiService & Partial<ModelApiService> & Partial<ScannerApiService> & Partial<OffloadConfigApiService> & Partial<StrategyGeneratorApiService>, remoteAddress: string, client: any): void {
	// Ensure the URL doesn't end with a slash
	const baseUrl = ((s: string) => {
		const url = remoteAddress.endsWith('/') ? remoteAddress.slice(0, -1) : remoteAddress;
		// 如果没有 http 协议头加上
		return url.startsWith('http') ? url : `http://${url}`;
	})(remoteAddress)
	
	apiService.getStrategyNames = async function(): Promise<string[]> {
		try {
			const response = await client.get(`${baseUrl}/strategy-generator/names`);
			return response.data;
		} catch (error) {
			throw new Error(`Failed to get strategy names: ${error}`);
		}
	};
	
	apiService.generateStrategy = async function(strategyName: string, scanResult: string, quantization: boolean): Promise<any[]> {
		try {
			const response = await client.post(`${baseUrl}/strategy-generator/generate`, {
				scan_result: scanResult,
				strategy_generator_name: strategyName
			}, {
				params: {
					quantization: quantization
				}
			});
			return response.data;
		} catch (error) {
			throw new Error(`Failed to generate strategy: ${error}`);
		}
	};
}

export interface DeployApiService {
  createDeployment(
    model_id: string,
    device: number,
    offload_id: number,
    model_kind?: "lm" | "t2v" | "t2i",
    enable_offload?: boolean,
    port?: number
  ): Promise<{ port: number }>;

  getPorts(model_id: string): Promise<{ ports: number[] }>;
  deviceCount(): Promise<{ count: number }>;
  stop(model_id: string, port: number): Promise<{ message: string }>
}

function addDeployApiMethods(
  apiService: ApiService &
    Partial<ModelApiService> &
    Partial<ScannerApiService> &
    Partial<OffloadConfigApiService> &
    Partial<StrategyGeneratorApiService> &
    Partial<DeployApiService>,
  remoteAddress: string,
  client: any
): void {
  const baseUrl = ((s: string) => {
    const url = remoteAddress.endsWith("/") ? remoteAddress.slice(0, -1) : remoteAddress;
    return url.startsWith("http") ? url : `http://${url}`;
  })(remoteAddress);

  // 🚀 创建部署
  apiService.createDeployment = async function (
    model_id: string,
    device: number,
    offload_id: number,
    model_kind: "lm" | "t2v" | "t2i" = "lm",
    enable_offload: boolean = false,
    port?: number
  ): Promise<{ port: number }> {
    try {
      const response = await client.post(`${baseUrl}/deploy/create`, null, {
        params: {
          model_id,
          device,
          offload_id,
          model_kind,
          enable_offload,
          port,
        },
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create deployment: ${error}`);
    }
  };

  // 📡 获取端口
  apiService.getPorts = async function (
    model_id: string
  ): Promise<{ ports: number[] }> {
    try {
      const response = await client.get(`${baseUrl}/deploy/ports/${model_id}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get ports: ${error}`);
    }
  };

  apiService.deviceCount = async function (): Promise<{ count: number }> {
    try {
      const response = await client.get(`${baseUrl}/deploy/device-count`);
      return response.data
    } catch (error) {
      throw new Error(`Failed to get device count: ${error}`);
    }
  };

  apiService.stop = async function (model_id: string, port: number): Promise<{ message: string }> {
    try {
      const response = await client.post(`${baseUrl}/deploy/stop`, null, {
        params: {
          model_id,
          port,
        },
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to stop deployment: ${error}`);
    }
  }
}


export function createApiService(remoteAddress: string, password: string) {
	// Ensure the URL doesn't end with a slash
	const baseUrl = ((s: string) => {
		const url = remoteAddress.endsWith('/') ? remoteAddress.slice(0, -1) : remoteAddress;
		// 如果没有 http 协议头加上
		return url.startsWith('http') ? url : `http://${url}`;
	})(remoteAddress)
	const client = getClient(remoteAddress, password);

	const apiService: ApiService & Partial<ModelApiService> & Partial<ScannerApiService> & Partial<OffloadConfigApiService> & Partial<StrategyGeneratorApiService> = {
		async ping(): Promise<string> {
			try {
				const response = await client.get(`${baseUrl}/ping`);
				return response.data;
			} catch (error) {
				throw new Error(`Failed to ping server: ${error}`);
			}
		},

		async authPing(): Promise<string> {
			try {
				const response = await client.get(`${baseUrl}/connect`);
				return response.data;
			} catch (error) {
				throw new Error(`Failed to ping server: ${error}`);
			}
		}
	};

	// 添加模型相关的API方法到apiService对象上
	addTorchModelApiMethods(apiService, remoteAddress, client);
	
	// 添加扫描相关的API方法到apiService对象上
	addScannerApiMethods(apiService, remoteAddress, client);

	// 添加offload config相关的API方法到apiService对象上
	addOffloadConfigApiMethods(apiService, remoteAddress, client);

	// 添加strategy generator相关的API方法到apiService对象上
	addStrategyGeneratorApiMethods(apiService, remoteAddress, client);
	addDeployApiMethods(apiService, remoteAddress, client);
	// 类型断言，因为我们知道此时apiService已经具备了所有方法
	return apiService as ApiService &
  ModelApiService &
  ScannerApiService &
  OffloadConfigApiService &
  StrategyGeneratorApiService &
  DeployApiService;
}

export async function verifyPwd(remoteAddress: string, password: string) {
  const apiService = createApiService(remoteAddress, password);
  try {
    await apiService.authPing();
    return true;
  } catch (error) {
    return false;
  }
}