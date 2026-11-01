#!/bin/bash -l
#SBATCH -J 1n4m16t-fast-soc
#SBATCH -N 1
#SBATCH --ntasks-per-node 16
#SBATCH --cpus-per-task 4
#SBATCH -o abacus.log
#SBATCH -e abacus.err
#SBATCH --time 24:00:00 
#SBATCH --partition xahcnormal


module purge
module use /work/share/acm4hzo7rg/modules/modulefiles
module load abacus/3.10
source $ABACUS_ENV_FILE
export OMP_NUM_THREADS=4
#export I_MPI_PIN_DOMAIN=socket

module list

echo $PATH

mpirun abacus | tee abacus_output
