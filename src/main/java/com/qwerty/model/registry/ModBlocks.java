package com.qwerty.model.registry;

import com.qwerty.model.QwertysModel;
import com.qwerty.model.block.DoorCameraBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.SoundType;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.material.MapColor;
import net.minecraft.world.level.material.PushReaction;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public final class ModBlocks {
    public static final DeferredRegister<Block> BLOCKS =
            DeferredRegister.create(ForgeRegistries.BLOCKS, QwertysModel.MODID);

    /** HT-100 style door camera, clean (as installed). */
    public static final RegistryObject<Block> HT100_DOOR_CAMERA =
            BLOCKS.register("ht100_door_camera", () -> new DoorCameraBlock(cameraProps()));

    /** HT-100 style door camera, aged (yellowed, removed from wall). */
    public static final RegistryObject<Block> HT100_DOOR_CAMERA_AGED =
            BLOCKS.register("ht100_door_camera_aged", () -> new DoorCameraBlock(cameraProps()));

    private static BlockBehaviour.Properties cameraProps() {
        return BlockBehaviour.Properties.of()
                .mapColor(MapColor.SAND)
                .strength(0.8F)
                .sound(SoundType.STONE)
                .noOcclusion()
                .pushReaction(PushReaction.DESTROY)
                .lightLevel(state -> state.getValue(DoorCameraBlock.LIT) ? 3 : 0);
    }

    private ModBlocks() {}
}
