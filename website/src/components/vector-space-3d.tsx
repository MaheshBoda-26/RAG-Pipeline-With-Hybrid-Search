"use client";

import * as React from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import {
  OrbitControls,
  Html,
  Points,
  Text,
  Sphere,
} from "@react-three/drei";
import { BufferGeometry, Float32BufferAttribute, PointsMaterial, Color } from "three";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ChunkData {
  id: string;
  x: number;
  y: number;
  z: number;
  source: string;
  strategy: string;
  text: string;
  role: "unretrieved" | "dense" | "sparse" | "reranked" | "query";
}

interface VectorSpace3DProps {
  chunks: ChunkData[];
  query?: string;
  isLoading?: boolean;
  className?: string;
  interactive?: boolean;
  width?: number | string;
  height?: number | string;
}

const NODE_COLORS = {
  unretrieved: { color: "#9AA3B2", size: 0.04, opacity: 0.3 },
  dense: { color: "#2554C7", size: 0.08, opacity: 1 },
  sparse: { color: "#5B6B85", size: 0.08, opacity: 1 },
  reranked: { color: "#7C3AED", size: 0.12, opacity: 1 },
  query: { color: "#15803D", size: 0.15, opacity: 1 },
};

function PointsCloud({ chunks, queryNode }: { chunks: ChunkData[]; queryNode: ChunkData | null }) {
  const positions: number[] = [];
  const colors: number[] = [];
  const sizes: number[] = [];
  const opacities: number[] = [];

  const color = new Color();

  chunks.forEach((chunk) => {
    const nodeColor = NODE_COLORS[chunk.role];
    positions.push(chunk.x, chunk.y, chunk.z);
    color.set(nodeColor.color);
    colors.push(color.r, color.g, color.b);
    sizes.push(nodeColor.size);
    opacities.push(nodeColor.opacity);
  });

  if (queryNode) {
    const nodeColor = NODE_COLORS.query;
    positions.push(queryNode.x, queryNode.y, queryNode.z);
    color.set(nodeColor.color);
    colors.push(color.r, color.g, color.b);
    sizes.push(nodeColor.size);
    opacities.push(nodeColor.opacity);
  }

  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new Float32BufferAttribute(colors, 3));
  geometry.setAttribute("size", new Float32BufferAttribute(sizes, 1));
  geometry.setAttribute("opacity", new Float32BufferAttribute(opacities, 1));

  return (
    <Points>
      <bufferGeometry attach="geometry" {...geometry} />
      <pointsMaterial
        attach="material"
        vertexColors
        sizeAttenuation
        transparent
        depthWrite={false}
        blending={2}
      />
    </Points>
  );
}

function Edges({ chunks, queryNode }: { chunks: ChunkData[]; queryNode: ChunkData | null }) {
  if (!queryNode) return null;

  const rerankedChunks = chunks.filter((c) => c.role === "reranked");
  const positions: number[] = [];

  rerankedChunks.forEach((chunk) => {
    positions.push(queryNode.x, queryNode.y, queryNode.z);
    positions.push(chunk.x, chunk.y, chunk.z);
  });

  if (positions.length === 0) return null;

  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));

  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial
        color="#5B6B85"
        transparent
        opacity={0.15}
        depthWrite={false}
      />
    </lineSegments>
  );
}

function NodeTooltip({
  chunk,
  visible,
  onClose,
}: {
  chunk: ChunkData | null;
  visible: boolean;
  onClose: () => void;
}) {
  if (!chunk || !visible) return null;

  const isQuery = chunk.role === "query";

  return (
    <Html
      transform
      position={[chunk.x, chunk.y + 0.3, chunk.z]}
      fullscreen
      distanceFactor={10}
      zIndexRange={[100, 100]}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: -10 }}
        transition={{ duration: 0.15, ease: [0.4, 0, 0.2, 1] }}
        className={cn(
          "pointer-events-auto px-3 py-2 rounded-md text-xs font-mono",
          "bg-neutral-950/95 dark:bg-neutral-50/95",
          "border border-neutral-200 dark:border-neutral-800",
          "shadow-lg backdrop-blur-sm max-w-xs",
          "text-neutral-50 dark:text-neutral-950"
        )}
        style={{
          transformOrigin: "center bottom",
          fontSize: "11px",
          lineHeight: "1.5",
        }}
      >
        <div className="flex items-center gap-1.5 mb-1.5">
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              chunk.role === "unretrieved" && "bg-neutral-400",
              chunk.role === "dense" && "bg-primary-600",
              chunk.role === "sparse" && "bg-secondary-500",
              chunk.role === "reranked" && "bg-accent-500",
              chunk.role === "query" && "bg-success-500"
            )}
          />
          <span className="font-medium text-neutral-100 dark:text-neutral-900 capitalize">
            {isQuery ? "Query Vector" : chunk.role}
          </span>
        </div>
        {!isQuery && (
          <>
            <div className="mb-1">
              <span className="text-neutral-400 dark:text-neutral-600">Source: </span>
              <span className="text-neutral-200 dark:text-neutral-800 truncate block max-w-[200px]">
                {chunk.source}
              </span>
            </div>
            <div className="mb-1">
              <span className="text-neutral-400 dark:text-neutral-600">Strategy: </span>
              <span className="text-neutral-200 dark:text-neutral-800 capitalize">
                {chunk.strategy}
              </span>
            </div>
            <div className="pt-1.5 border-t border-neutral-800 dark:border-neutral-200">
              <span className="text-neutral-400 dark:text-neutral-600">Preview: </span>
              <span className="text-neutral-300 dark:text-neutral-700">
                {chunk.text.slice(0, 120)}...
              </span>
            </div>
          </>
        )}
        {isQuery && (
          <div className="text-neutral-400 dark:text-neutral-600">
            Your question projected into vector space
          </div>
        )}
      </motion.div>
    </Html>
  );
}

function CameraController({
  chunks,
  queryNode,
  activeQuery,
}: {
  chunks: ChunkData[];
  queryNode: ChunkData | null;
  activeQuery: boolean;
}) {
  const { camera } = useThree();
  const targetRef = React.useRef({ x: 0, y: 0, z: 0 });
  const currentRef = React.useRef({ x: 0, y: 0, z: 0 });

  useFrame((_, dt) => {
    if (!activeQuery) {
      camera.position.x = Math.sin(Date.now() * 0.000002) * 15;
      camera.position.z = Math.cos(Date.now() * 0.000002) * 15;
      camera.lookAt(0, 0, 0);
      return;
    }

    if (queryNode) {
      targetRef.current.x = queryNode.x;
      targetRef.current.y = queryNode.y;
      targetRef.current.z = queryNode.z;
    } else if (chunks.length > 0) {
      const reranked = chunks.filter((c) => c.role === "reranked");
      if (reranked.length > 0) {
        const avgX = reranked.reduce((a, c) => a + c.x, 0) / reranked.length;
        const avgY = reranked.reduce((a, c) => a + c.y, 0) / reranked.length;
        const avgZ = reranked.reduce((a, c) => a + c.z, 0) / reranked.length;
        targetRef.current.x = avgX;
        targetRef.current.y = avgY;
        targetRef.current.z = avgZ;
      }
    }

    const lerpFactor = 1 - Math.pow(0.001, dt);
    currentRef.current.x += (targetRef.current.x - currentRef.current.x) * lerpFactor;
    currentRef.current.y += (targetRef.current.y - currentRef.current.y) * lerpFactor;
    currentRef.current.z += (targetRef.current.z - currentRef.current.z) * lerpFactor;

    camera.position.x += (currentRef.current.x - camera.position.x) * 0.02;
    camera.position.y += (currentRef.current.y + 3 - camera.position.y) * 0.02;
    camera.position.z += (currentRef.current.z + 8 - camera.position.z) * 0.02;
    camera.lookAt(currentRef.current.x, currentRef.current.y, currentRef.current.z);
  });

  return null;
}

function VectorSpaceScene({
  chunks,
  query,
  interactive = true,
}: {
  chunks: ChunkData[];
  query?: string;
  interactive: boolean;
}) {
  const queryNode = chunks.find((c) => c.role === "query") || null;
  const activeQuery = !!query;
  const [hoveredChunk, setHoveredChunk] = React.useState<ChunkData | null>(null);

  const handlePointerOver = (event: ThreeEvent<PointerEvent>, chunk: ChunkData) => {
    if (!interactive) return;
    event.stopPropagation();
    setHoveredChunk(chunk);
  };

  const handlePointerOut = () => {
    setHoveredChunk(null);
  };

  return (
    <>
      <fog attach="fog" args={["#FFFFFF", 8, 40]} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[10, 10, 5]} intensity={0.8} />
      <directionalLight position={[-10, -5, -5]} intensity={0.4} />

      <PointsCloud chunks={chunks} queryNode={queryNode} />
      <Edges chunks={chunks} queryNode={queryNode} />

      {chunks.map((chunk) => (
        <Sphere
          key={chunk.id}
          position={[chunk.x, chunk.y, chunk.z]}
          args={[NODE_COLORS[chunk.role].size, 16, 16]}
          onPointerOver={(e) => handlePointerOver(e, chunk)}
          onPointerOut={handlePointerOut}
          visible={false}
        >
          <meshBasicMaterial
            transparent
            opacity={0}
            color={NODE_COLORS[chunk.role].color}
          />
        </Sphere>
      ))}

      {queryNode && (
        <Sphere
          position={[queryNode.x, queryNode.y, queryNode.z]}
          args={[NODE_COLORS.query.size, 8, 8]}
        >
          <meshBasicMaterial color={NODE_COLORS.query.color} />
        </Sphere>
      )}

      <NodeTooltip chunk={hoveredChunk} visible={!!hoveredChunk} onClose={() => setHoveredChunk(null)} />

      <CameraController chunks={chunks} queryNode={queryNode} activeQuery={activeQuery} />

      {interactive && (
        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          enablePan
          enableZoom
          minDistance={3}
          maxDistance={50}
          autoRotate={!activeQuery}
          autoRotateSpeed={0.2}
        />
      )}
    </>
  );
}

export function VectorSpace3D({
  chunks,
  query,
  isLoading = false,
  className,
  interactive = true,
  width = "100%",
  height = "100%",
}: VectorSpace3DProps) {
  if (isLoading || chunks.length === 0) {
    return (
      <div
        className={cn("relative w-full h-full bg-neutral-50 dark:bg-neutral-950 rounded-lg", className)}
        style={{ width, height }}
        aria-label="Vector space visualization loading"
      >
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center text-neutral-400 dark:text-neutral-600">
            <div className="w-8 h-8 border-2 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm font-medium">Computing projection...</p>
            <p className="text-xs mt-1">UMAP reduction of 1536-dim embeddings</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn("relative w-full h-full rounded-lg overflow-hidden", className)}
      style={{ width, height }}
      aria-label={query ? "Interactive vector space visualization with query results" : "Vector space visualization of indexed documents"}
    >
      <Canvas
        camera={{ position: [0, 3, 15], fov: 45 }}
        style={{ width: "100%", height: "100%" }}
        gl={{ antialias: true, alpha: true, preserveDrawingBuffer: false }}
      >
        <VectorSpaceScene chunks={chunks} query={query} interactive={interactive} />
      </Canvas>

      {!interactive && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center text-neutral-400 dark:text-neutral-600 px-4">
            <p className="text-sm font-medium mb-1">Live Corpus Visualization</p>
            <p className="text-xs">Visit the dashboard to explore</p>
          </div>
        </div>
      )}

      {query && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute bottom-4 left-4 right-4 md:left-auto md:right-4 md:bottom-auto md:top-4 md:w-72"
        >
          <div className="bg-neutral-950/95 dark:bg-neutral-50/95 backdrop-blur-sm rounded-md border border-neutral-200 dark:border-neutral-800 p-3 text-xs">
            <div className="flex items-center gap-2 mb-2 text-neutral-400 dark:text-neutral-600">
              <span className="w-2 h-2 rounded-full bg-accent-500" />
              <span className="font-medium text-neutral-100 dark:text-neutral-900">Reranked Finalists</span>
            </div>
            <div className="flex items-center gap-2 mb-1 text-neutral-400 dark:text-neutral-600">
              <span className="w-2 h-2 rounded-full bg-primary-600" />
              <span className="font-medium text-neutral-100 dark:text-neutral-900">Dense Matches</span>
            </div>
            <div className="flex items-center gap-2 mb-1 text-neutral-400 dark:text-neutral-600">
              <span
                className="w-2 h-2 rounded-full border border-secondary-500 bg-transparent"
              />
              <span className="font-medium text-neutral-100 dark:text-neutral-900">Sparse Matches</span>
            </div>
            <div className="flex items-center gap-2 mb-1 text-neutral-400 dark:text-neutral-600">
              <span className="w-2 h-2 rounded-full bg-neutral-400 opacity-30" />
              <span className="font-medium text-neutral-100 dark:text-neutral-900">Unretrieved</span>
            </div>
            <div className="flex items-center gap-2 text-neutral-400 dark:text-neutral-600">
              <span className="w-2 h-2 rounded-full bg-success-500" />
              <span className="font-medium text-neutral-100 dark:text-neutral-900">Query Vector</span>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}