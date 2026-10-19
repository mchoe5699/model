package com.qwerty.model.block;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.LevelAccessor;
import net.minecraft.world.level.LevelReader;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.level.gameevent.GameEvent;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;

import javax.annotation.Nullable;

/**
 * Wall-mounted apartment door camera (HT-100 style).
 * <ul>
 *   <li>FACING points away from the wall (the side the lens looks at).</li>
 *   <li>Right-click the call button: "ding-dong" chime, button LED lights,
 *       redstone signal 15 for about 1.6 seconds (like a doorbell).</li>
 *   <li>Sneak + right-click the front: toggle the night IR LEDs (glows faintly).</li>
 * </ul>
 */
public class DoorCameraBlock extends HorizontalDirectionalBlock {
    /** 0 = idle, 2 = "ding" played, 1 = "dong" played (still powered). */
    public static final IntegerProperty CALL = IntegerProperty.create("call", 0, 2);
    public static final BooleanProperty LIT = BlockStateProperties.LIT;

    private static final VoxelShape SHAPE_NORTH = Block.box(3.0D, 1.5D, 12.4D, 13.0D, 14.5D, 16.0D);
    private static final VoxelShape SHAPE_SOUTH = Block.box(3.0D, 1.5D, 0.0D, 13.0D, 14.5D, 3.6D);
    private static final VoxelShape SHAPE_EAST = Block.box(0.0D, 1.5D, 3.0D, 3.6D, 14.5D, 13.0D);
    private static final VoxelShape SHAPE_WEST = Block.box(12.4D, 1.5D, 3.0D, 16.0D, 14.5D, 13.0D);

    private static final int DING_TO_DONG_TICKS = 8;
    private static final int DONG_TO_RELEASE_TICKS = 24;

    public DoorCameraBlock(Properties properties) {
        super(properties);
        registerDefaultState(stateDefinition.any()
                .setValue(FACING, Direction.NORTH)
                .setValue(CALL, 0)
                .setValue(LIT, false));
    }

    @Override
    protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder) {
        builder.add(FACING, CALL, LIT);
    }

    // ---------------------------------------------------------------- shape / placement

    @Override
    public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context) {
        return switch (state.getValue(FACING)) {
            case SOUTH -> SHAPE_SOUTH;
            case EAST -> SHAPE_EAST;
            case WEST -> SHAPE_WEST;
            default -> SHAPE_NORTH;
        };
    }

    @Override
    public boolean canSurvive(BlockState state, LevelReader level, BlockPos pos) {
        Direction facing = state.getValue(FACING);
        BlockPos wall = pos.relative(facing.getOpposite());
        return level.getBlockState(wall).isFaceSturdy(level, wall, facing);
    }

    @Override
    public BlockState updateShape(BlockState state, Direction direction, BlockState neighborState,
                                  LevelAccessor level, BlockPos pos, BlockPos neighborPos) {
        if (direction == state.getValue(FACING).getOpposite() && !state.canSurvive(level, pos)) {
            return Blocks.AIR.defaultBlockState();
        }
        return super.updateShape(state, direction, neighborState, level, pos, neighborPos);
    }

    @Nullable
    @Override
    public BlockState getStateForPlacement(BlockPlaceContext context) {
        BlockState base = defaultBlockState();
        for (Direction look : context.getNearestLookingDirections()) {
            if (look.getAxis().isHorizontal()) {
                BlockState candidate = base.setValue(FACING, look.getOpposite());
                if (candidate.canSurvive(context.getLevel(), context.getClickedPos())) {
                    return candidate;
                }
            }
        }
        return null;
    }

    // ---------------------------------------------------------------- interaction

    @Override
    @SuppressWarnings("deprecation")
    public InteractionResult use(BlockState state, Level level, BlockPos pos, Player player,
                                 InteractionHand hand, BlockHitResult hit) {
        if (hit.getDirection() != state.getValue(FACING)) {
            return InteractionResult.PASS;
        }

        if (player.isShiftKeyDown()) {
            if (!level.isClientSide) {
                BlockState toggled = state.cycle(LIT);
                level.setBlock(pos, toggled, Block.UPDATE_ALL);
                level.playSound(null, pos, SoundEvents.STONE_BUTTON_CLICK_ON, SoundSource.BLOCKS, 0.25F, 1.6F);
                player.displayClientMessage(Component.translatable(toggled.getValue(LIT)
                        ? "message.qwertys_model.door_camera.ir_on"
                        : "message.qwertys_model.door_camera.ir_off"), true);
            }
            return InteractionResult.sidedSuccess(level.isClientSide);
        }

        if (!isOnCallButton(state, pos, hit.getLocation())) {
            return InteractionResult.PASS;
        }
        if (state.getValue(CALL) > 0) {
            return InteractionResult.CONSUME;
        }

        if (!level.isClientSide) {
            level.setBlock(pos, state.setValue(CALL, 2), Block.UPDATE_ALL);
            level.playSound(null, pos, SoundEvents.STONE_BUTTON_CLICK_ON, SoundSource.BLOCKS, 0.3F, 1.3F);
            chime(level, pos, 1.26F); // "ding" (E)
            updateNeighbours(state, level, pos);
            level.scheduleTick(pos, this, DING_TO_DONG_TICKS);
            level.gameEvent(player, GameEvent.BLOCK_ACTIVATE, pos);
            player.displayClientMessage(Component.translatable("message.qwertys_model.door_camera.call"), true);
        }
        return InteractionResult.sidedSuccess(level.isClientSide);
    }

    /** True when the hit point lies on the square call button (lower right, seen from the front). */
    private static boolean isOnCallButton(BlockState state, BlockPos pos, Vec3 hitLocation) {
        Direction right = state.getValue(FACING).getCounterClockWise(); // viewer's right-hand side
        double lx = hitLocation.x - (pos.getX() + 0.5D);
        double lz = hitLocation.z - (pos.getZ() + 0.5D);
        double across = (lx * right.getStepX() + lz * right.getStepZ()) * 16.0D; // px from centre toward viewer's right
        double up = (hitLocation.y - pos.getY()) * 16.0D;
        return across >= 0.75D && across <= 4.25D && up >= 2.25D && up <= 6.0D;
    }

    private static void chime(Level level, BlockPos pos, float pitch) {
        level.playSound(null, pos, SoundEvents.NOTE_BLOCK_CHIME.value(), SoundSource.BLOCKS, 1.0F, pitch);
        level.playSound(null, pos, SoundEvents.NOTE_BLOCK_BELL.value(), SoundSource.BLOCKS, 0.35F, pitch);
    }

    @Override
    @SuppressWarnings("deprecation")
    public void tick(BlockState state, ServerLevel level, BlockPos pos, RandomSource random) {
        int call = state.getValue(CALL);
        if (call == 2) {
            chime(level, pos, 1.0F); // "dong" (C)
            level.setBlock(pos, state.setValue(CALL, 1), Block.UPDATE_ALL);
            level.scheduleTick(pos, this, DONG_TO_RELEASE_TICKS);
        } else if (call == 1) {
            BlockState released = state.setValue(CALL, 0);
            level.setBlock(pos, released, Block.UPDATE_ALL);
            level.playSound(null, pos, SoundEvents.STONE_BUTTON_CLICK_OFF, SoundSource.BLOCKS, 0.3F, 1.1F);
            updateNeighbours(released, level, pos);
            level.gameEvent(null, GameEvent.BLOCK_DEACTIVATE, pos);
        }
    }

    // ---------------------------------------------------------------- redstone

    @Override
    @SuppressWarnings("deprecation")
    public boolean isSignalSource(BlockState state) {
        return true;
    }

    @Override
    @SuppressWarnings("deprecation")
    public int getSignal(BlockState state, BlockGetter level, BlockPos pos, Direction direction) {
        return state.getValue(CALL) > 0 ? 15 : 0;
    }

    @Override
    @SuppressWarnings("deprecation")
    public int getDirectSignal(BlockState state, BlockGetter level, BlockPos pos, Direction direction) {
        return state.getValue(CALL) > 0 && direction == state.getValue(FACING) ? 15 : 0;
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onRemove(BlockState state, Level level, BlockPos pos, BlockState newState, boolean isMoving) {
        if (!isMoving && !state.is(newState.getBlock()) && state.getValue(CALL) > 0) {
            updateNeighbours(state, level, pos);
        }
        super.onRemove(state, level, pos, newState, isMoving);
    }

    private void updateNeighbours(BlockState state, Level level, BlockPos pos) {
        level.updateNeighborsAt(pos, this);
        level.updateNeighborsAt(pos.relative(state.getValue(FACING).getOpposite()), this);
    }
}
