export interface AudioIODevice {
  index: number;
  name: string;
}

export interface LoopbackDevice {
  index: number;
  name: string;
  sample_rate: number;
  channels: number;
}

export interface AudioSessionApp {
  pid: number;
  executable: string;
  display_name: string;
  is_active: boolean;
}

export interface VoiceOption {
  id: string;
  engine: "edge";
  gender: string;
  style: string;
}
